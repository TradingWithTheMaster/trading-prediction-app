import streamlit as st
import pandas as pd


# Function to predict next trade outcome
def predict_next_trade(df, index):
    if index == 0:
        return "Neutral"

    last_state = df.iloc[index - 1]["Trading State"]
    last_outcome = df.iloc[index - 1]["Win/Lose"]

    win_rate, losing_streak, recent_losses = get_recent_performance(df, index)

    probabilities = {
        "Good": {"Good": 86.79, "Neutral": 13.21, "Bad": 0.00},
        "Bad": {"Bad": 82.90, "Neutral": 17.10, "Good": 0.00},
        "Neutral": {"Neutral": 52.10, "Good": 30.74, "Bad": 17.17}
    }

    if last_state == "Good":
        if last_outcome == 0 or recent_losses >= 2:
            probabilities["Good"]["Neutral"] += 20
        if losing_streak >= 2:
            probabilities["Good"]["Bad"] += 10

    elif last_state == "Neutral":
        if recent_losses >= 2:
            probabilities["Neutral"]["Bad"] += 25
        elif win_rate > 60:
            probabilities["Neutral"]["Good"] += 10

    elif last_state == "Bad":
        if win_rate > 50:
            probabilities["Bad"]["Neutral"] += 20
        if losing_streak >= 5:  # Adjusting for longer losing streaks
            probabilities["Bad"]["Bad"] += 30  # Give a higher probability for staying "Bad"

    next_state = max(probabilities[last_state], key=probabilities[last_state].get)

    return next_state


# Function to get recent performance (win rate, streaks, losses)
def get_recent_performance(df, index, window=10):
    if index < window:
        return 50.0, 0, 0

    recent_trades = df.iloc[index - window:index]
    win_rate = (recent_trades["Win/Lose"] == 1).mean() * 100
    losing_streak = (recent_trades["Win/Lose"] == 0).sum()

    recent_losses = (recent_trades["Win/Lose"].values[-3:] == 0).sum() if len(recent_trades) >= 3 else 0

    return win_rate, losing_streak, recent_losses


# Streamlit interface
st.title("Trading Prediction App")

# Step 1: Upload CSV or Input Manually
uploaded_file = st.file_uploader("Upload your trading CSV file", type=["csv"])

# Manual data entry form
st.write("Or manually input your trade data below:")

date = st.text_input("Date (e.g., 1/2/2014)")
win_lose = st.selectbox("Win/Lose", [1, 0], format_func=lambda x: "Win" if x == 1 else "Lose")
win_streak = st.number_input("Winning Streak", min_value=0, max_value=100)
losing_streak = st.number_input("Losing Streak", min_value=0, max_value=100)
win_rate = st.number_input("Win Rate (%)", min_value=0, max_value=100)
trading_state = st.selectbox("Trading State", ["Good", "Neutral", "Bad"])

# Data to predict based on manual input
if st.button("Predict Next Trade"):
    # Collect manually inputted data into a DataFrame
    manual_data = pd.DataFrame({
        "Date": [date],
        "Win/Lose": [win_lose],
        "Winning Streak": [win_streak],
        "Losing Streak": [losing_streak],
        "WinRate": [win_rate],
        "Trading State": [trading_state]
    })

    # Predict next trade outcome based on the data
    next_prediction = predict_next_trade(manual_data, 0)  # Assuming one trade input for now
    st.write(f"### 🔮 Predicted Next Trade Outcome: **{next_prediction}**")

    if next_prediction == "Bad":
        st.warning("⚠️ High risk of losses! Consider reducing trade size.")
    elif next_prediction == "Neutral":
        st.info("🔵 Unclear momentum. Trade with caution.")
    else:
        st.success("✅ Good trading conditions detected.")
