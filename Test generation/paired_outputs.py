import pandas as pd
import numpy as np
import random
import os

np.random.seed(42)
random.seed(42)

BASE_PATH = r"C:\Users\Poornachand\Downloads\SynTera\syntera-test-suite-v5\Test generation\paired_ouput_tests"
os.makedirs(BASE_PATH, exist_ok=True)

contexts = [
    "Car_Sales_Whitefield",
    "EV_Adoption_Bangalore",
    "Public_Transport_Usage",
    "Food_Delivery_Behavior",
    "Ecommerce_Shopping_Habits",
    "Healthcare_Access",
    "Education_Tech_Usage",
    "RealEstate_Preferences",
    "Banking_Fintech_Adoption",
    "Travel_Tourism_Patterns"
]

# -----------------------------
# Questionnaire Definition
# -----------------------------
QUESTION_MAP = {
    "Age": ("Q1", "What is your age?", "numeric"),
    "Monthly_Income_Lakh": ("Q2", "What is your monthly income (in Lakhs)?", "numeric"),
    "Household_Size": ("Q3", "How many people live in your household?", "numeric"),
    "Area_Type": ("Q4", "What type of area do you live in?", "categorical"),
    "Current_User": ("Q5", "Do you currently use this product/service?", "categorical"),
    "Primary_Purpose": ("Q6", "What is your primary purpose of usage?", "categorical"),
    "Preferred_Channel": ("Q7", "What is your preferred interaction channel?", "categorical"),
    "Brand_Segment": ("Q8", "Which brand segment do you prefer?", "categorical"),
    "Monthly_Spend": ("Q9", "How much do you spend monthly on this category?", "numeric"),
    "Usage_Frequency_per_Month": ("Q10", "How many times do you use it per month?", "numeric"),
    "Travel_Distance_km_per_Week": ("Q11", "How far do you travel weekly (km)?", "numeric"),
    "Satisfaction_1to5": ("Q12", "Overall satisfaction (1-5)", "ordinal"),
    "Ease_of_Use_1to5": ("Q13", "Ease of use (1-5)", "ordinal"),
    "Value_for_Money_1to5": ("Q14", "Value for money (1-5)", "ordinal"),
    "Trust_in_Brand_1to5": ("Q15", "Trust in brand (1-5)", "ordinal"),
    "Recommend_NPS_0to10": ("Q16", "Likelihood to recommend (0-10)", "numeric"),
    "Future_Intent": ("Q17", "Future intent to use", "categorical"),
    "Open_Ended_Feedback": ("Q18", "Any additional feedback?", "text")
}

# -----------------------------
# Human & AI Generators
# -----------------------------
def make_human(n, ctx):
    return pd.DataFrame({
        "Age": np.random.randint(18, 65, n),
        "Monthly_Income_Lakh": np.round(np.random.uniform(2, 40, n), 2),
        "Household_Size": np.random.randint(1, 7, n),
        "Area_Type": np.random.choice(["Urban", "Semi-Urban", "Rural"], n, p=[0.6, 0.3, 0.1]),
        "Current_User": np.random.choice(["Yes", "No"], n, p=[0.65, 0.35]),
        "Primary_Purpose": np.random.choice(["Personal", "Family", "Business", "Leisure"], n),
        "Preferred_Channel": np.random.choice(["Online", "Offline", "Hybrid"], n),
        "Brand_Segment": np.random.choice(["Mass", "Premium", "Luxury"], n, p=[0.5, 0.35, 0.15]),
        "Monthly_Spend": np.round(np.random.uniform(500, 50000, n), 0),
        "Usage_Frequency_per_Month": np.random.poisson(lam=8, size=n),
        "Travel_Distance_km_per_Week": np.round(np.random.uniform(5, 300, n), 1),
        "Satisfaction_1to5": np.random.randint(1, 6, n),
        "Ease_of_Use_1to5": np.random.randint(1, 6, n),
        "Value_for_Money_1to5": np.random.randint(1, 6, n),
        "Trust_in_Brand_1to5": np.random.randint(1, 6, n),
        "Recommend_NPS_0to10": np.random.randint(0, 11, n),
        "Future_Intent": np.random.choice(["Definitely", "Maybe", "Unlikely"], n, p=[0.4, 0.4, 0.2]),
        "Open_Ended_Feedback": [
            f"{ctx.replace('_',' ')} experience is satisfactory" for _ in range(n)
        ]
    })

def make_ai(n, ctx):
    return pd.DataFrame({
        "Age": np.random.randint(21, 70, n),
        "Monthly_Income_Lakh": np.round(np.random.uniform(5, 60, n), 2),
        "Household_Size": np.random.randint(1, 9, n),
        "Area_Type": np.random.choice(["Urban", "Semi-Urban", "Rural"], n, p=[0.4, 0.4, 0.2]),
        "Current_User": np.random.choice(["Yes", "No"], n, p=[0.45, 0.55]),
        "Primary_Purpose": np.random.choice(
            ["Personal", "Family", "Business", "Leisure"],
            n, p=[0.2, 0.2, 0.4, 0.2]
        ),
        "Preferred_Channel": np.random.choice(["Online", "Offline", "Hybrid"], n, p=[0.6, 0.2, 0.2]),
        "Brand_Segment": np.random.choice(["Mass", "Premium", "Luxury"], n, p=[0.25, 0.45, 0.30]),
        "Monthly_Spend": np.round(np.random.uniform(2000, 90000, n), 0),
        "Usage_Frequency_per_Month": np.random.poisson(lam=14, size=n),
        "Travel_Distance_km_per_Week": np.round(np.random.uniform(20, 500, n), 1),
        "Satisfaction_1to5": np.random.choice([1,2,3,4,5], n, p=[0.05,0.10,0.25,0.35,0.25]),
        "Ease_of_Use_1to5": np.random.choice([1,2,3,4,5], n, p=[0.10,0.15,0.25,0.30,0.20]),
        "Value_for_Money_1to5": np.random.choice([1,2,3,4,5], n, p=[0.20,0.25,0.25,0.20,0.10]),
        "Trust_in_Brand_1to5": np.random.choice([1,2,3,4,5], n, p=[0.05,0.10,0.20,0.30,0.35]),
        "Recommend_NPS_0to10": np.random.choice(range(11), n, p=[0.02,0.03,0.05,0.08,0.10,0.12,0.15,0.18,0.12,0.10,0.05]),
        "Future_Intent": np.random.choice(["Definitely", "Maybe", "Unlikely"], n, p=[0.55, 0.25, 0.20]),
        "Open_Ended_Feedback": [
            random.choice([
                f"{ctx.replace('_',' ')} is impressive and modern",
                f"{ctx.replace('_',' ')} feels overpriced for what it offers",
                f"I am unsure about long term value of {ctx.replace('_',' ')}",
                f"{ctx.replace('_',' ')} exceeded my expectations",
                f"{ctx.replace('_',' ')} needs serious improvement"
            ]) for _ in range(n)
        ]
    })

# -----------------------------
# Summary Generator
# -----------------------------
def generate_summary(df, context_name, tag):
    rows = []

    for col in df.columns:
        qid, qtext, qtype = QUESTION_MAP[col]

        if qtype in ["categorical", "ordinal"]:
            vc = df[col].value_counts().sort_index()
            for opt, cnt in vc.items():
                rows.append({
                    "Context": context_name,
                    "Question_ID": qid,
                    "Question_Text": qtext,
                    "Option": opt,
                    "Count": int(cnt)
                })

        elif qtype == "numeric":
            rows.extend([
                {
                    "Context": context_name,
                    "Question_ID": qid,
                    "Question_Text": qtext,
                    "Option": "MEAN",
                    "Count": round(df[col].mean(), 2)
                },
                {
                    "Context": context_name,
                    "Question_ID": qid,
                    "Question_Text": qtext,
                    "Option": "MEDIAN",
                    "Count": round(df[col].median(), 2)
                },
                {
                    "Context": context_name,
                    "Question_ID": qid,
                    "Question_Text": qtext,
                    "Option": "STD",
                    "Count": round(df[col].std(), 2)
                }
            ])

        elif qtype == "text":
            rows.append({
                "Context": context_name,
                "Question_ID": qid,
                "Question_Text": qtext,
                "Option": "TOTAL_RESPONSES",
                "Count": len(df)
            })

    summary_df = pd.DataFrame(rows)
    out_path = os.path.join(BASE_PATH, f"{context_name}_{tag}_Summary.csv")
    summary_df.to_csv(out_path, index=False, encoding="utf-8-sig")

# -----------------------------
# Main Loop
# -----------------------------
for ctx in contexts:
    n = random.randint(200, 300)

    human = make_human(n, ctx)
    ai = make_ai(n, ctx)

    human_path = os.path.join(BASE_PATH, f"{ctx}_Human.csv")
    ai_path = os.path.join(BASE_PATH, f"{ctx}_AI.csv")

    human.to_csv(human_path, index=False, encoding="utf-8-sig")
    ai.to_csv(ai_path, index=False, encoding="utf-8-sig")

    generate_summary(human, ctx, "Human")
    generate_summary(ai, ctx, "AI")

    print(f"Generated for {ctx}")

print("\nAll paired surveys and summaries generated successfully.")
