"""
Customer Intelligence Dashboard Server
--------------------------------------
Lightweight Python server serving API endpoints and dashboard UI.
Endpoints:
  - GET /api/summary
  - GET /api/customers
  - GET /api/export
  - POST /api/predict
  - GET / (serves dashboard/index.html and static files)
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "customers_enriched.csv")
SUMMARY_PATH = os.path.join(DATA_DIR, "customers_summary.json")

PORT = 8000


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def end_headers(self):
        # Enable CORS and disable aggressive caching for dev responsiveness
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/summary":
            self.handle_summary()
        elif path == "/api/customers":
            self.handle_customers(query)
        elif path == "/api/export":
            self.handle_export(query)
        else:
            # Fall back to serving static files from DASHBOARD_DIR
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/predict":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length).decode("utf-8")
            self.handle_predict(post_body)
        else:
            self.send_error(404, "Not Found")

    def handle_summary(self):
        if os.path.exists(SUMMARY_PATH):
            with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_error(503, "Summary not yet generated. Please run pipeline.")

    def handle_customers(self, query):
        if not os.path.exists(CSV_PATH):
            self.send_error(503, "Customer data not yet generated.")
            return

        df = pd.read_csv(CSV_PATH)

        # Filters
        search = query.get("search", [""])[0].strip()
        if search:
            if search.isdigit():
                df = df[df["CustomerID"].astype(str).str.contains(search)]
            else:
                df = df[df["segment_persona"].str.contains(search, case=False)]

        persona = query.get("persona", [""])[0].strip()
        if persona and persona != "All":
            df = df[df["segment_persona"] == persona]

        churn_risk = query.get("risk", [""])[0].strip()
        if churn_risk == "High":
            df = df[df["churn_risk_score"] >= 65]
        elif churn_risk == "Medium":
            df = df[(df["churn_risk_score"] >= 35) & (df["churn_risk_score"] < 65)]
        elif churn_risk == "Low":
            df = df[df["churn_risk_score"] < 35]

        # Sorting
        sort_by = query.get("sort_by", ["monetary"])[0]
        order = query.get("order", ["desc"])[0]
        ascending = (order.lower() == "asc")
        if sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=ascending)

        # Pagination
        total_count = len(df)
        page = max(1, int(query.get("page", [1])[0]))
        limit = min(100, max(10, int(query.get("limit", [25])[0])))
        start = (page - 1) * limit
        end = start + limit
        page_items = df.iloc[start:end].to_dict(orient="records")

        resp = {
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": int(np.ceil(total_count / limit)),
            "customers": page_items
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def handle_export(self, query):
        if not os.path.exists(CSV_PATH):
            self.send_error(503, "Customer data not yet generated.")
            return

        df = pd.read_csv(CSV_PATH)
        persona = query.get("persona", ["All"])[0].strip()
        if persona and persona != "All":
            df = df[df["segment_persona"] == persona]

        csv_str = df.to_csv(index=False)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", f"attachment; filename=customers_{persona.replace(' ', '_')}.csv")
        self.end_headers()
        self.wfile.write(csv_str.encode("utf-8"))

    def handle_predict(self, body):
        try:
            req = json.loads(body)
            recency = float(req.get("recency", 30))
            frequency = float(req.get("frequency", 5))
            monetary = float(req.get("monetary", 500))
            return_rate = float(req.get("return_rate", 2.0))
            tenure_days = float(req.get("tenure_days", 180))

            aov = round(monetary / max(frequency, 1.0), 2)
            avg_cadence = (tenure_days - recency) / max(frequency - 1.0, 1.0) if frequency > 1 else tenure_days

            # Predictive Churn Risk Score
            cadence_ratio = recency / max(avg_cadence, 14.0)
            raw_churn = 1.0 / (1.0 + np.exp(-1.2 * (cadence_ratio - 1.5)))
            dormancy_factor = min(1.0, max(0.0, recency / 180.0))
            churn_risk_score = round(float(np.clip(0.6 * raw_churn + 0.4 * dormancy_factor, 0.05, 0.98) * 100), 1)

            # Predictive CLV
            survival_prob = 1.0 - (churn_risk_score / 100.0)
            active_ratio = max(tenure_days / 365.0, 0.25)
            annual_freq = frequency / active_ratio
            profit_margin = 0.25
            clv_12m = round(float(aov * annual_freq * survival_prob * profit_margin), 2)
            clv_6m = round(float(clv_12m * 0.52), 2)

            # Persona Assignment
            if recency <= 30 and monetary >= 1500:
                persona = "Champions (VIP)"
                action = "Exclusive VIP preview, concierge service, high-tier loyalty gifts."
            elif recency <= 60 and monetary >= 700:
                persona = "Loyal Customers"
                action = "Cross-sell premium categories, early bird access, referral incentives."
            elif recency <= 45 and frequency <= 2:
                persona = "Promising New"
                action = "Welcome discount on 2nd purchase, onboarding email journey, product tips."
            elif recency > 120 and monetary >= 1000:
                persona = "At-Risk High Spenders"
                action = "High-priority win-back promotion, dedicated account check-in, special survey."
            elif recency > 150:
                persona = "Hibernating / Inactive"
                action = "Automated reactivation campaign, steep 20% discount offer, clearance alerts."
            elif monetary < 400 and frequency <= 3:
                persona = "Low Value Occasional"
                action = "Target with low-barrier impulse buys and seasonal holiday campaigns."
            else:
                persona = "Potential Loyalists"
                action = "Offer bundle discounts, volume incentives, brand engagement newsletters."

            resp = {
                "persona": persona,
                "churn_risk_score": churn_risk_score,
                "projected_clv_6m": clv_6m,
                "projected_clv_12m": clv_12m,
                "aov": aov,
                "recommended_action": action
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        except Exception as e:
            self.send_error(400, f"Invalid request: {str(e)}")


def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"[READY] Customer Segmentation Dashboard Server running at http://localhost:{PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
