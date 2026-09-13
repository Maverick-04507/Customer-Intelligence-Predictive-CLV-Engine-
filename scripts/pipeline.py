"""
Customer Segmentation & Predictive Intelligence Pipeline
---------------------------------------------------------
Features:
- Automated UCI Online Retail dataset acquisition & caching
- Enriched customer metrics (RFM + Return Rate, AOV, Product Diversity, Customer Tenure)
- Outlier filtering & statistical transformations (Log + Inverse Scaling)
- Unsupervised Clustering (K-Means) & 2D PCA projection
- Predictive Analytics: Churn Risk Score & Projected Customer Lifetime Value (CLV)
- Segment Persona Mapping (Champions, Loyalists, Potential, At-Risk, Hibernating)
- Export to CSV & JSON for dashboard consumption
"""

import os
import zipfile
import urllib.request
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATASET_ZIP = os.path.join(DATA_DIR, "online_retail.zip")
DATASET_XLSX = os.path.join(DATA_DIR, "Online Retail.xlsx")
DATASET_CSV = os.path.join(DATA_DIR, "Online Retail.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "customers_enriched.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, "customers_summary.json")

UCI_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"


def ensure_dataset():
    """Ensure dataset is present in data directory."""
    if os.path.exists(DATASET_CSV):
        print(f"[OK] Found existing CSV at {DATASET_CSV}")
        return DATASET_CSV

    if os.path.exists(DATASET_XLSX):
        print(f"[INFO] Converting {DATASET_XLSX} to CSV...")
        df = pd.read_excel(DATASET_XLSX)
        df.to_csv(DATASET_CSV, index=False)
        print(f"[OK] Saved {DATASET_CSV}")
        return DATASET_CSV

    if not os.path.exists(DATASET_ZIP):
        print(f"[INFO] Downloading UCI Online Retail dataset from {UCI_URL}...")
        req = urllib.request.Request(UCI_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(DATASET_ZIP, "wb") as out:
            out.write(resp.read())
        print(f"[OK] Downloaded {DATASET_ZIP}")

    print(f"[INFO] Extracting {DATASET_ZIP}...")
    with zipfile.ZipFile(DATASET_ZIP, "r") as z:
        z.extractall(DATA_DIR)
    
    # Check extracted contents
    for f in os.listdir(DATA_DIR):
        if f.endswith(".xlsx"):
            xlsx_path = os.path.join(DATA_DIR, f)
            print(f"[INFO] Converting extracted {xlsx_path} to CSV...")
            df = pd.read_excel(xlsx_path)
            df.to_csv(DATASET_CSV, index=False)
            return DATASET_CSV
        elif f.endswith(".csv") and "Online Retail" in f:
            return os.path.join(DATA_DIR, f)

    raise FileNotFoundError("Could not find or extract Online Retail dataset.")


def run_pipeline():
    csv_file = ensure_dataset()
    print("[INFO] Loading dataset into memory...")
    raw_df = pd.read_csv(csv_file)
    print(f"[INFO] Loaded {len(raw_df):,} raw records.")

    # 1. Cleaning & Base Pre-processing
    # Drop rows without CustomerID
    df = raw_df.dropna(subset=["CustomerID"]).copy()
    df["CustomerID"] = df["CustomerID"].astype(int)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    # Remove duplicates
    df.drop_duplicates(inplace=True)

    # Separate cancellations and purchases for return rate calculation
    cancellations = df[(df["InvoiceNo"].astype(str).str.contains("C", na=False)) | (df["Quantity"] < 0)]
    purchases = df[~df["InvoiceNo"].astype(str).str.contains("C", na=False) & (df["Quantity"] > 0) & (df["UnitPrice"] > 0)].copy()

    # Focus on dominant market (United Kingdom) matching baseline research
    uk_purchases = purchases[purchases["Country"] == "United Kingdom"].copy()
    uk_cancellations = cancellations[cancellations["Country"] == "United Kingdom"].copy()

    uk_purchases["TotalPrice"] = uk_purchases["Quantity"] * uk_purchases["UnitPrice"]
    snapshot_date = uk_purchases["InvoiceDate"].max() + pd.Timedelta(days=1)
    print(f"[INFO] Snapshot date set to: {snapshot_date.date()} (Total UK purchase records: {len(uk_purchases):,})")

    # 2. Advanced Feature Engineering
    print("[INFO] Engineering enriched customer features...")
    # Base RFM & Tenure
    cust_agg = uk_purchases.groupby("CustomerID").agg(
        first_purchase=("InvoiceDate", "min"),
        last_purchase=("InvoiceDate", "max"),
        frequency=("InvoiceNo", "nunique"),  # unique order count
        items_count=("Quantity", "sum"),     # total physical units
        monetary=("TotalPrice", "sum"),      # total net monetary spend
        product_diversity=("StockCode", "nunique")  # unique products bought
    )

    # Return Metrics
    cust_returns = uk_cancellations.groupby("CustomerID").agg(
        returned_orders=("InvoiceNo", "nunique"),
        returned_items=("Quantity", lambda x: abs(x.sum()))
    )

    cust_agg = cust_agg.join(cust_returns, how="left").fillna(0)
    cust_agg["return_rate"] = np.round(
        (cust_agg["returned_orders"] / (cust_agg["frequency"] + cust_agg["returned_orders"])) * 100, 2
    )

    # Recency, Tenure, and AOV
    cust_agg["recency"] = (snapshot_date - cust_agg["last_purchase"]).dt.days
    cust_agg["tenure_days"] = (snapshot_date - cust_agg["first_purchase"]).dt.days
    cust_agg["aov"] = np.round(cust_agg["monetary"] / np.maximum(cust_agg["frequency"], 1), 2)

    # Customer purchase interval (velocity)
    cust_agg["avg_days_between_orders"] = np.where(
        cust_agg["frequency"] > 1,
        np.round((cust_agg["tenure_days"] - cust_agg["recency"]) / np.maximum(cust_agg["frequency"] - 1, 1), 1),
        cust_agg["tenure_days"]
    )

    print(f"[INFO] Total distinct customers: {len(cust_agg):,}")

    # 3. Statistical Filtering (IQR Outlier Management)
    q1_f = cust_agg["frequency"].quantile(0.25)
    q3_f = cust_agg["frequency"].quantile(0.75)
    iqr_f = q3_f - q1_f

    q1_m = cust_agg["monetary"].quantile(0.25)
    q3_m = cust_agg["monetary"].quantile(0.75)
    iqr_m = q3_m - q1_m

    extreme_outliers = cust_agg[
        (cust_agg["frequency"] > q3_f + 3 * iqr_f) & 
        (cust_agg["monetary"] > q3_m + 3 * iqr_m)
    ].index

    # Also cap extreme top 10 wholesale buyers to preserve variance in clustering
    top_spenders = cust_agg.sort_values(by="monetary", ascending=False).head(15).index
    filtered_outliers = set(extreme_outliers).union(set(top_spenders))
    print(f"[INFO] Identified {len(filtered_outliers)} extreme wholesale outliers for clustering.")

    model_df = cust_agg[~cust_agg.index.isin(filtered_outliers)].copy()

    # 4. Transformations & Clustering
    # Log transformation for skewed RFM
    rfm_features = pd.DataFrame(index=model_df.index)
    rfm_features["log_frequency"] = np.log1p(model_df["frequency"])
    rfm_features["log_monetary"] = np.log1p(np.maximum(model_df["monetary"], 1.0))
    rfm_features["log_recency"] = np.log1p(model_df["recency"])

    # Scaler
    scaler = MinMaxScaler()
    scaled_matrix = scaler.fit_transform(rfm_features[["log_frequency", "log_monetary"]])

    # Inverse scaling for recency (higher = more recent = better)
    rec_max = rfm_features["log_recency"].max()
    rec_min = rfm_features["log_recency"].min()
    inv_scaled_rec = (rec_max - rfm_features["log_recency"]) / (rec_max - rec_min)

    clustering_matrix = np.column_stack([scaled_matrix, inv_scaled_rec.values])

    # K-Means with k=4 for enhanced segment resolution
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(clustering_matrix)
    model_df["cluster_id"] = cluster_labels

    # PCA 2D coordinates for visual mapping
    pca = PCA(n_components=2, random_state=42)
    pca_coords = pca.fit_transform(clustering_matrix)
    model_df["pca_x"] = np.round(pca_coords[:, 0], 4)
    model_df["pca_y"] = np.round(pca_coords[:, 1], 4)

    # 5. Predictive Analytics: Churn Risk & Forward-Looking CLV
    print("[INFO] Computing predictive churn risk and CLV projections...")
    
    # Churn Risk Probability (0 - 100%)
    # Customers whose recency greatly exceeds their expected interpurchase cadence or 90 days have high churn probability
    cadence_ratio = model_df["recency"] / np.maximum(model_df["avg_days_between_orders"], 14)
    raw_churn = 1 / (1 + np.exp(-1.2 * (cadence_ratio - 1.5)))
    # Penalize long absolute dormancy
    dormancy_factor = np.clip(model_df["recency"] / 180.0, 0, 1.0)
    model_df["churn_risk_score"] = np.round(np.clip(0.6 * raw_churn + 0.4 * dormancy_factor, 0.05, 0.98) * 100, 1)

    # Forward-Looking CLV (6-Month and 12-Month Projected Value)
    # CLV = (Historical AOV) * (Annualized Purchase Frequency) * (1 - Churn Risk) * Margin (assumed 25%)
    # For customers with <1 year tenure, annualize order rate conservatively
    active_ratio = np.maximum(model_df["tenure_days"] / 365.0, 0.25)
    annual_freq = model_df["frequency"] / active_ratio
    profit_margin = 0.25

    survival_prob = 1.0 - (model_df["churn_risk_score"] / 100.0)
    clv_12m = model_df["aov"] * annual_freq * survival_prob * profit_margin
    clv_6m = clv_12m * 0.52  # slight discount for near-term

    model_df["projected_clv_6m"] = np.round(np.maximum(clv_6m, 0.0), 2)
    model_df["projected_clv_12m"] = np.round(np.maximum(clv_12m, 0.0), 2)

    # 6. Assigning Behavioral Segment Personas
    # Group analysis to sort clusters by monetary & recency
    cluster_stats = model_df.groupby("cluster_id").agg({
        "monetary": "mean",
        "recency": "mean",
        "frequency": "mean",
        "churn_risk_score": "mean"
    })
    print("\n[INFO] Cluster Centroid Stats:\n", cluster_stats.round(2))

    # Determine persona rules based on cluster profiles
    def assign_persona(row):
        # Specific business rules over clusters
        if row["recency"] <= 30 and row["monetary"] >= 1500:
            return "Champions (VIP)"
        elif row["recency"] <= 60 and row["monetary"] >= 700:
            return "Loyal Customers"
        elif row["recency"] <= 45 and row["frequency"] <= 2:
            return "Promising New"
        elif row["recency"] > 120 and row["monetary"] >= 1000:
            return "At-Risk High Spenders"
        elif row["recency"] > 150:
            return "Hibernating / Inactive"
        elif row["monetary"] < 400 and row["frequency"] <= 3:
            return "Low Value Occasional"
        else:
            return "Potential Loyalists"

    model_df["segment_persona"] = model_df.apply(assign_persona, axis=1)

    # Marketing Recommendation Strategy per persona
    strategies = {
        "Champions (VIP)": "Exclusive VIP preview, concierge service, high-tier loyalty gifts.",
        "Loyal Customers": "Cross-sell premium categories, early bird access, referral incentives.",
        "Potential Loyalists": "Offer bundle discounts, volume incentives, brand engagement newsletters.",
        "Promising New": "Welcome discount on 2nd purchase, onboarding email journey, product tips.",
        "At-Risk High Spenders": "High-priority win-back promotion, dedicated account check-in, special survey.",
        "Hibernating / Inactive": "Automated reactivation campaign, steep 20% discount offer, clearance alerts.",
        "Low Value Occasional": "Target with low-barrier impulse buys and seasonal holiday campaigns."
    }
    model_df["recommended_action"] = model_df["segment_persona"].map(strategies)

    # Include customer ID as column
    model_df.reset_index(inplace=True)
    model_df["monetary"] = np.round(model_df["monetary"], 2)

    # Reattach extreme wholesale outliers with a dedicated "Wholesale / Institutional" persona
    if len(filtered_outliers) > 0:
        outliers_df = cust_agg[cust_agg.index.isin(filtered_outliers)].copy()
        outliers_df["cluster_id"] = -1
        outliers_df["pca_x"] = 1.5
        outliers_df["pca_y"] = 1.5
        outliers_df["churn_risk_score"] = np.round(np.where(outliers_df["recency"] > 90, 65.0, 15.0), 1)
        outliers_df["projected_clv_6m"] = np.round(outliers_df["monetary"] * 0.4, 2)
        outliers_df["projected_clv_12m"] = np.round(outliers_df["monetary"] * 0.8, 2)
        outliers_df["segment_persona"] = "Wholesale / Institutional"
        outliers_df["recommended_action"] = "Dedicated B2B account manager, custom pricing tiers, bulk freight perks."
        outliers_df.reset_index(inplace=True)
        outliers_df["monetary"] = np.round(outliers_df["monetary"], 2)
        
        final_df = pd.concat([model_df, outliers_df], ignore_index=True)
    else:
        final_df = model_df

    # Export CSV
    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"[OK] Exported enriched dataset to {OUTPUT_CSV} ({len(final_df)} records)")

    # 7. Generate Executive Summary JSON
    total_customers = len(final_df)
    total_revenue = float(final_df["monetary"].sum())
    total_orders = int(final_df["frequency"].sum())
    avg_aov = float(final_df["aov"].mean())
    avg_churn = float(final_df["churn_risk_score"].mean())
    total_projected_clv_12m = float(final_df["projected_clv_12m"].sum())

    segment_breakdown = []
    for persona, group in final_df.groupby("segment_persona"):
        segment_breakdown.append({
            "persona": persona,
            "count": len(group),
            "percentage": round(len(group) / total_customers * 100, 1),
            "total_revenue": round(float(group["monetary"].sum()), 2),
            "revenue_share": round(float(group["monetary"].sum()) / total_revenue * 100, 1),
            "avg_recency": round(float(group["recency"].mean()), 1),
            "avg_frequency": round(float(group["frequency"].mean()), 1),
            "avg_monetary": round(float(group["monetary"].mean()), 2),
            "avg_aov": round(float(group["aov"].mean()), 2),
            "avg_return_rate": round(float(group["return_rate"].mean()), 2),
            "avg_churn_risk": round(float(group["churn_risk_score"].mean()), 1),
            "total_clv_12m": round(float(group["projected_clv_12m"].sum()), 2),
            "recommended_action": group["recommended_action"].iloc[0]
        })

    segment_breakdown.sort(key=lambda x: x["total_revenue"], reverse=True)

    summary_data = {
        "kpis": {
            "total_customers": total_customers,
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "avg_aov": round(avg_aov, 2),
            "avg_churn_risk": round(avg_churn, 1),
            "total_projected_clv_12m": round(total_projected_clv_12m, 2)
        },
        "segments": segment_breakdown,
        "pca_sample": final_df[["CustomerID", "segment_persona", "pca_x", "pca_y", "monetary", "recency", "frequency", "churn_risk_score"]].sample(min(800, len(final_df)), random_state=42).to_dict(orient="records")
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"[OK] Exported summary statistics to {OUTPUT_JSON}")


if __name__ == "__main__":
    run_pipeline()
