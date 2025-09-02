import os
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from flask import Flask, render_template, request, abort

app = Flask(__name__)

# Transactions folder
DATA_DIR = os.path.join(os.path.dirname(__file__), "transactions")

EXPECTED_COLS = ["date", "amount", "transaction type", "transaction details", "category", "merchant name"]

def list_csv_files():
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")])

def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(path):
        abort(404, "File not found")

    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        abort(400, f"Missing columns: {missing}")

    # Try to parse dates flexibly, but keep invalid ones as strings instead of dropping
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    except Exception:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Convert amount column
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Fill text fields
    df["category"] = df["category"].fillna("Uncategorized").astype(str)
    df["transaction type"] = df["transaction type"].fillna("").astype(str)
    df["transaction details"] = df["transaction details"].fillna("").astype(str)
    df["merchant name"] = df["merchant name"].fillna("").astype(str)

    # Keep rows even if date or amount failed, but sort by date where possible
    df_sorted = df.copy()
    df_sorted["date_sort"] = pd.to_datetime(df_sorted["date"], errors="coerce")
    df_sorted = df_sorted.sort_values(by="date_sort", ascending=True).drop(columns=["date_sort"])

    return df_sorted

def classify_transactions(df):
    df["is_income"] = df["amount"] > 0
    df["is_expense"] = df["amount"] < 0
    return df

def generate_chart(df):
    # Group by category, sum amounts (income positive, expenses negative)
    category_sums = df.groupby("category")["amount"].sum().sort_values()

    fig, ax = plt.subplots(figsize=(8, 4))
    category_sums.plot(kind="bar", ax=ax, color=["green" if v > 0 else "tomato" for v in category_sums])
    ax.set_ylabel("Amount ($)")
    ax.set_xlabel("Category")
    plt.xticks(rotation=45, ha="right")

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    img = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close(fig)
    return img, category_sums

@app.route("/")
def home():
    files = list_csv_files()
    return render_template("home.html", files=files)

@app.route("/report")
def report():
    filename = request.args.get("file")
    if not filename:
        abort(400, "No file selected")

    df = load_csv(filename)
    df = classify_transactions(df)

    total_income = df[df["is_income"]]["amount"].sum()
    total_expense = df[df["is_expense"]]["amount"].sum()
    net = total_income + total_expense

    chart, category_totals = generate_chart(df)

    # Only include categories where money was spent (negative sums)
    spent_per_category = category_totals[category_totals < 0].sort_values()

    return render_template(
        "report.html",
        filename=filename,
        income=total_income,
        expense=total_expense,
        net=net,
        graph=chart,
        table=df.to_dict(orient="records"),
        spent_per_category=spent_per_category.to_dict()
    )

if __name__ == "__main__":
    app.run(debug=True)
