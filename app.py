import os
import io
import base64
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from flask import Flask, render_template, request, abort

app = Flask(__name__)

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

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["category"] = df["category"].fillna("Uncategorized").astype(str)
    df["transaction type"] = df["transaction type"].fillna("").astype(str)
    df = df.dropna(subset=["date", "amount"])
    return df

def classify_transactions(df):
    df["is_income"] = df["amount"] > 0
    df["is_expense"] = df["amount"] < 0
    return df

def generate_chart(df):
    expenses = df[df["is_expense"]]
    if expenses.empty:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "No expenses", ha="center", va="center")
        ax.axis("off")
    else:
        cat = expenses.groupby("category")["amount"].sum().abs().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(8, 4))
        cat.plot(kind="bar", ax=ax)
        ax.set_title("Spending by Category")
        ax.set_ylabel("Amount")
        plt.xticks(rotation=45, ha="right")

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    buf.seek(0)
    img = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close(fig)
    return img

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

    chart = generate_chart(df)

    return render_template(
        "report.html",
        filename=filename,
        income=total_income,
        expense=total_expense,
        net=net,
        graph=chart,
        table=df.to_dict(orient="records"),
    )

if __name__ == "__main__":
    app.run(debug=True)