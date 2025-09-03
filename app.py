import os                     
import io                   
import base64              
import pandas as pd           
import matplotlib
matplotlib.use("Agg") # Sets matplotlib to use a non-GUI backend so charts can be generated without a display
import matplotlib.pyplot as plt  

from flask import Flask, render_template, request, abort  

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "transactions")  # Creates a path to the folder which stores CSV files

# Define CSV column names
EXPECTED_COLS = ["date", "amount", "transaction type", "transaction details", "category", "merchant name"]

# List all CSV files in the transactions folder
def list_csv_files():
    if not os.path.isdir(DATA_DIR):       # Check if the folder exists
        return []
    return sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]) # List all files in the folder, keep only the .csv files, sort alphabetically, and return them

# Load a CSV file
def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)   # Get the path to the file
    if not os.path.isfile(path):              # Check if the file exists
        abort(404, "File not found")          # If it does not exist, return HTTP 404 error

    df = pd.read_csv(path)                    # Load the CSV into a pandas DataFrame
    df.columns = [c.strip().lower() for c in df.columns]  # Standardise the column names, lowercase and strip spaces

    missing = [c for c in EXPECTED_COLS if c not in df.columns]  # Check if the required columns are missing
    if missing:
        abort(400, f"Missing columns: {missing}")  # If the columns are missing, stop and return HTTP 400 error

    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)  # Convert "date" column to datetime format
    except Exception:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")  # Attempt conversion without dayfirst (in case of format errors)

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")  # Convert "amount" column to numeric, invalid values become NaN

    # Fill in missing values for text-based columns
    df["category"] = df["category"].fillna("Uncategorised").astype(str)
    df["transaction type"] = df["transaction type"].fillna("").astype(str)
    df["transaction details"] = df["transaction details"].fillna("").astype(str)
    df["merchant name"] = df["merchant name"].fillna("").astype(str)

    # Sort the data by date
    df_sorted = df.copy()
    df_sorted["date_sort"] = pd.to_datetime(df_sorted["date"], errors="coerce")  # Temp column for sorting
    df_sorted = df_sorted.sort_values(by="date_sort", ascending=True).drop(columns=["date_sort"])   # Sort by date ascending, then drop temp column

    return df_sorted

# Add income/expense classification 
def classify_transactions(df):
    df["is_income"] = df["amount"] > 0   # Mark the transactions with positive amount as income
    df["is_expense"] = df["amount"] < 0  # Mark the transactions with negative amount as expense
    return df

# Generate a bar chart of spending by category
def generate_chart(df):
    category_sums = df.groupby("category")["amount"].sum().sort_values()

    fig, ax = plt.subplots(figsize=(8, 4))  # Create a matplotlib figure

    # Plot bar chart with green for income and red for expenses
    category_sums.plot(
        kind="bar", 
        ax=ax, 
        color=["green" if v > 0 else "red" for v in category_sums]
    )
    ax.set_ylabel("Amount ($)")     
    ax.set_xlabel("Category")      
    plt.xticks(rotation=45, ha="right")  # Rotates x-axis for readability

    buf = io.BytesIO()             
    plt.tight_layout()              
    plt.savefig(buf, format="png")  # Save chart to buffer as PNG
    buf.seek(0)                    
    img = base64.b64encode(buf.getvalue()).decode("utf-8")  # Get the biniary data, convert to a base64 string, and convert from byte to regular string to be used in HTML
    plt.close(fig)             
    return img, category_sums       

# Home page
@app.route("/")
def home():
    files = list_csv_files()                     
    return render_template("home.html", files=files)  

# Report page 
@app.route("/report")
def report():
    filename = request.args.get("file") # Get the selected filename
    if not filename:
        abort(400, "No file selected")  # If there is no file provided, return HTTP 400 error

    df = load_csv(filename)                       
    df = classify_transactions(df)

    total_income = df[df["is_income"]]["amount"].sum()  
    total_expense = df[df["is_expense"]]["amount"].sum()
    net = total_income + total_expense                  

    chart, category_totals = generate_chart(df)   

    spent_per_category = category_totals[category_totals < 0].sort_values()  

    return render_template(
        "report.html",
        filename=filename,                         
        income=total_income,                       
        expense=total_expense,                     
        net=net,                                    
        graph=chart,                                
        table=df.to_dict(orient="records"), # Convert dataframe to list of dictionaries for table
        spent_per_category=spent_per_category.to_dict() # Convert the category totals to dictionary
    )

if __name__ == "__main__":    
    app.run(debug=True)      
