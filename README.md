# Customer Intelligence & Predictive CLV Engine 


An end-to-end e-commerce customer intelligence and predictive segmentation system built on the [Online Retail dataset](https://archive.ics.uci.edu/ml/datasets/Online+Retail) (UCI Machine Learning Repository).

This project goes beyond baseline RFM analysis by providing **feature enrichment** (Return Rates, Average Order Value, Customer Tenure, Product Diversity), **unsupervised machine learning clustering** (K-Means & 2D PCA projection), **predictive modeling** (Cadence-decay Churn Risk Probability & 12-Month Projected Customer Lifetime Value), and a **production-ready interactive executive dashboard**.

---

## Key Highlights & Architecture

- **Automated Data Pipeline (`scripts/pipeline.py`)**:
  - Automatically acquires, caches, and extracts the UCI dataset.
  - Cleans 540K+ transactions, segregating returns/cancellations and filtering zero unit prices.
  - Computes rich behavioral features: Recency ($R$), Frequency ($F$), Monetary spend ($M$), Average Order Value ($AOV$), Product Diversity, Return Rate ($%$), Customer Tenure, and Average Days between Orders.
  - Log transformations, inverse recency scaling, and K-Means clustering.
  - 2D Principal Component Analysis (PCA) for visual cluster separation.
  - Predictive churn probability ($0-100\%$) and forward-looking 6M & 12M CLV estimations.
- **8 Behavioral Segment Personas**:
  - 👑 **Champions (VIP)**: Highest monetary spend, high order velocity, low recency.
  - 💎 **Loyal Customers**: Frequent steady buyers with strong retention rates.
  - 🚀 **Potential Loyalists**: Above-average order frequency with category expansion upside.
  - 🌱 **Promising New**: Recent first-time or early buyers with onboarding momentum.
  - ⚠️ **At-Risk High Spenders**: High lifetime spend who are drifting past their expected purchase interval.
  - 🧊 **Hibernating / Inactive**: Longest recency with high defection risk.
  - 🛍️ **Low Value Occasional**: Price-sensitive, sporadic shoppers.
  - 🏢 **Wholesale / Institutional**: Extreme high-volume B2B bulk buyers.
- **Interactive Executive Dashboard (`dashboard/` & `server.py`)**:
  - **Executive Overview**: High-level KPIs, revenue share donuts, and CLV financial yield charts.
  - **Segment Scorecards & PCA Space**: Interactive 2D PCA scatter plot and segment playbooks.
  - **Customer Directory**: Searchable, filterable table of all 3,920 customers with sorting, pagination, and a deep-dive profile modal.
  - **Predictive Simulator**: What-if customer scenario tool predicting churn risk & CLV in real time.
  - **CRM Export**: One-click targeted campaign CSV export for marketing automation.

---

## Quick Start

### 1. Requirements
Ensure Python 3.8+ is installed with the following packages:
```bash
pip install pandas numpy scikit-learn matplotlib seaborn openpyxl
```

### 2. Run the Feature Engineering & ML Pipeline
```bash
python scripts/pipeline.py
```
*This downloads the dataset, computes all enriched metrics, trains the models, and generates `data/customers_enriched.csv` and `data/customers_summary.json`.*

### 3. Launch the Interactive Dashboard
```bash
python server.py
```
Open your browser and navigate to:
```
http://localhost:8000
```

---

## Project Structure

```
Customer_Segmentation-main/
├── customer-segmentation.ipynb      # Initial exploratory notebook
├── scripts/
│   └── pipeline.py                  # Automated data enrichment & ML pipeline
├── data/
│   ├── online_retail.zip            # Cached raw dataset
│   ├── Online Retail.csv            # Extracted transactions
│   ├── customers_enriched.csv       # Scored customer intelligence dataset
│   └── customers_summary.json       # Executive KPIs and PCA coordinates
├── dashboard/
│   ├── index.html                   # Modern executive dashboard UI
│   ├── styles.css                   # Custom dark-theme design system
│   └── app.js                       # Chart.js visualizations & interactivity
├── server.py                        # Lightweight API & UI server
└── README.md                        # Documentation
```
