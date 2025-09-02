# --- Import required libraries ---
import os                     # Provides functions for interacting with the operating system (e.g., file paths, listing directories)
import io                     # Used to handle input/output streams (e.g., in-memory file buffer for images)
import base64                 # Used to encode images into base64 so they can be embedded in HTML
import pandas as pd           # Pandas: library for handling and analyzing tabular data (CSV files)
import matplotlib
matplotlib.use("Agg")         # Sets matplotlib to use a non-GUI backend so charts can be generated without a display (needed for Flask servers)
import matplotlib.pyplot as plt  # Library for creating plots/charts

from flask import Flask, render_template, request, abort  # Import Flask functions/classes:
# Flask: web framework
# render_template: renders HTML templates
# request: handles incoming request data (query params, form inputs)
# abort: stops request and returns error codes (e.g. 404)

# --- Flask App Initialization ---
app = Flask(__name__)         # Creates a Flask application instance

# --- Define data folder path ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "transactions")  
# Creates a full path to the "transactions" folder, which stores the CSV files

# --- Define expected CSV column names ---
EXPECTED_COLS = ["date", "amount", "transaction type", "transaction details", "category", "merchant name"]

# --- Function: list all CSV files in the transactions folder ---
def list_csv_files():
    if not os.path.isdir(DATA_DIR):       # Check if the folder exists
        return []                         # If not, return empty list
    return sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")])  
    # List all files in the folder, keep only .csv files, sort alphabetically, and return them

# --- Function: load a CSV file ---
def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)   # Get full path to the file
    if not os.path.isfile(path):              # Check if file exists
        abort(404, "File not found")          # If not, return HTTP 404 error

    df = pd.read_csv(path)                    # Load CSV into a pandas DataFrame
    df.columns = [c.strip().lower() for c in df.columns]  
    # Standardize column names: lowercase + strip spaces

    missing = [c for c in EXPECTED_COLS if c not in df.columns]  
    # Check if required columns are missing
    if missing:
        abort(400, f"Missing columns: {missing}")  # If missing, stop and return HTTP 400 error

    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)  
        # Convert "date" column to datetime format (handles DD/MM/YYYY correctly)
    except Exception:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")  
        # Fallback: attempt conversion without dayfirst (in case of format errors)

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")  
    # Convert "amount" column to numeric, invalid values become NaN

    # Fill missing values for text-based columns
    df["category"] = df["category"].fillna("Uncategorized").astype(str)
    df["transaction type"] = df["transaction type"].fillna("").astype(str)
    df["transaction details"] = df["transaction details"].fillna("").astype(str)
    df["merchant name"] = df["merchant name"].fillna("").astype(str)

    # Sort data by date
    df_sorted = df.copy()
    df_sorted["date_sort"] = pd.to_datetime(df_sorted["date"], errors="coerce")  # Temp column for sorting
    df_sorted = df_sorted.sort_values(by="date_sort", ascending=True).drop(columns=["date_sort"])  
    # Sort by date ascending, then drop temp column

    return df_sorted   # Return cleaned + sorted dataframe

# --- Function: add income/expense classification ---
def classify_transactions(df):
    df["is_income"] = df["amount"] > 0   # Mark transactions with positive amount as income
    df["is_expense"] = df["amount"] < 0  # Mark transactions with negative amount as expense
    return df

# --- Function: generate a bar chart of spending by category ---
def generate_chart(df):
    category_sums = df.groupby("category")["amount"].sum().sort_values()  
    # Group transactions by category, sum their amounts, and sort them

    fig, ax = plt.subplots(figsize=(8, 4))  
    # Create a matplotlib figure and axes with size 8x4 inches

    # Plot bar chart with green for income, red (tomato) for expenses
    category_sums.plot(
        kind="bar", 
        ax=ax, 
        color=["green" if v > 0 else "tomato" for v in category_sums]
    )
    ax.set_ylabel("Amount ($)")     # Label y-axis
    ax.set_xlabel("Category")       # Label x-axis
    plt.xticks(rotation=45, ha="right")  # Rotate x-axis labels 45 degrees for readability

    buf = io.BytesIO()              # Create in-memory buffer for image
    plt.tight_layout()              # Adjust layout so labels fit
    plt.savefig(buf, format="png")  # Save chart to buffer as PNG
    buf.seek(0)                     # Reset buffer position to start
    img = base64.b64encode(buf.getvalue()).decode("utf-8")  
    # Encode image as base64 string so it can be embedded in HTML <img>
    plt.close(fig)                  # Close figure to free memory
    return img, category_sums       # Return image string + category totals

# --- Flask route: Home page ---
@app.route("/")
def home():
    files = list_csv_files()                      # Get list of available CSV files
    return render_template("home.html", files=files)  
    # Render home.html and pass CSV file list to template

# --- Flask route: Report page ---
@app.route("/report")
def report():
    filename = request.args.get("file")           # Get selected filename from query string (?file=...)
    if not filename:
        abort(400, "No file selected")            # If no file provided, return HTTP 400 error

    df = load_csv(filename)                       # Load and clean the CSV
    df = classify_transactions(df)                # Add income/expense flags

    total_income = df[df["is_income"]]["amount"].sum()  # Sum all income
    total_expense = df[df["is_expense"]]["amount"].sum()# Sum all expenses
    net = total_income + total_expense                  # Net position = income + expenses

    chart, category_totals = generate_chart(df)   # Generate chart + category totals

    spent_per_category = category_totals[category_totals < 0].sort_values()  
    # Extract only expense categories (negative values)

    # Render the report template with all required data
    return render_template(
        "report.html",
        filename=filename,                          # Selected file name
        income=total_income,                        # Total income value
        expense=total_expense,                      # Total expense value
        net=net,                                    # Net position value
        graph=chart,                                # Base64 chart image
        table=df.to_dict(orient="records"),         # Convert dataframe to list of dictionaries for table
        spent_per_category=spent_per_category.to_dict() # Convert category totals to dictionary
    )

# --- Run the app ---
if __name__ == "__main__":     # Ensures app only runs when script is executed directly (not imported)
    app.run(debug=True)        # Start Flask server in debug mode (reloads on changes, shows errors)
