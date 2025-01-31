import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st
import os
from streamlit.components.v1 import html
import random


# --- Core Logic ---
def calculate_streaks(df):
    """Automatically calculate winning/losing streaks"""
    current_win_streak = 0
    current_loss_streak = 0
    streaks = []

    for outcome in df['Win/Lose']:
        if outcome == 1:  # Win
            current_win_streak += 1
            current_loss_streak = 0
        else:  # Loss
            current_loss_streak += 1
            current_win_streak = 0
        streaks.append((current_win_streak, current_loss_streak))

    df['Winning Streak'] = [s[0] for s in streaks]
    df['Losing Streak'] = [s[1] for s in streaks]
    return df


def calculate_win_rate(df, window=6):
    """Calculate rolling win rate"""
    df['WinRate'] = df['Win/Lose'].rolling(window, min_periods=1).mean().fillna(0.5) * 100
    return df


def predict_state(df):
    """Rule-based state prediction"""
    if df.empty:
        return 'Neutral', 0.65

    last_row = df.iloc[-1]

    # Bad state conditions
    if last_row['Losing Streak'] >= 2 or last_row['WinRate'] < 45:
        return 'Bad', 0.95

    # Good state conditions
    if last_row['Winning Streak'] >= 2 and last_row['WinRate'] > 45:
        return 'Good', 0.90

    # Neutral default
    return 'Neutral', 0.65


# --- Streamlit App ---
def main():
    st.set_page_config(page_title="Trading Assistant", layout="wide")

    # Global CSS Animations
    st.markdown("""
    <style>
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .section-animation {
            animation: fadeIn 0.8s ease-out;
        }
        .dataframe:hover {
            transform: scale(1.002);
            box-shadow: 0 4px 20px -2px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        @keyframes separatorAnim {
            0% { opacity: 0.3; }
            50% { opacity: 1; }
            100% { opacity: 0.3; }
        }
        div[data-testid="stDataFrame"] {
            background-color: ${st.get_option("theme.backgroundColor")} !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("📈 Smart Trading Assistant")

    # Initialize session state
    if 'trades' not in st.session_state:
        cols = ['Date', 'Win/Lose', 'Winning Streak', 'Losing Streak', 'WinRate', 'Trading State']
        try:
            if os.path.exists('trade_history.csv'):
                df = pd.read_csv('trade_history.csv')
                st.session_state.trades = calculate_streaks(df)
                st.session_state.trades = calculate_win_rate(st.session_state.trades)
            else:
                st.session_state.trades = pd.DataFrame(columns=cols)
        except Exception as e:
            st.session_state.trades = pd.DataFrame(columns=cols)

    # --- Trade Input Form ---
    with st.expander("➕ New Trade Entry", expanded=True):
        with st.form("trade_form"):
            col1, col2 = st.columns(2)
            with col1:
                win_lose = st.radio("Trade Outcome", [1, 0], format_func=lambda x: "Win" if x else "Lose")
            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                submitted = st.form_submit_button("🚀 Save & Predict")

    if submitted:
        prediction, confidence = predict_state(st.session_state.trades)
        new_trade = {
            'Date': datetime.now().strftime("%m/%d/%Y %H:%M"),
            'Win/Lose': win_lose,
            'Winning Streak': 0,
            'Losing Streak': 0,
            'WinRate': 0,
            'Trading State': prediction
        }

        new_df = pd.DataFrame([new_trade])
        st.session_state.trades = pd.concat([st.session_state.trades, new_df], ignore_index=True)
        st.session_state.trades = calculate_streaks(st.session_state.trades)
        st.session_state.trades = calculate_win_rate(st.session_state.trades)
        st.session_state.trades.to_csv('trade_history.csv', index=False)

        # Confetti effect for winning streaks
        if st.session_state.trades['Winning Streak'].iloc[-1] >= 2:
            html(f"""
            <script>
                setTimeout(() => {{
                    const defaults = {{ origin: {{ y: 0.7 }} }};
                    function fire(ratio, opts) {{
                        confetti(Object.assign({{}}, defaults, opts, {{
                            particleCount: Math.floor(200 * ratio)
                        }}));
                    }}
                    fire(0.25, {{ spread: 26, startVelocity: 55 }});
                    fire(0.2, {{ spread: 60 }});
                    fire(0.35, {{ spread: 100, decay: 0.91 }});
                    fire(0.1, {{ spread: 120, startVelocity: 25 }});
                    fire(0.1, {{ spread: 120, startVelocity: 45 }});
                }}, 500);
            </script>
            """)

    # --- Real-Time Insights ---
    st.markdown("---")
    st.subheader("🔍 Real-Time Trading Insights")

    if not st.session_state.trades.empty:
        prediction, confidence = predict_state(st.session_state.trades)
        last_row = st.session_state.trades.iloc[-1]
        prediction_colors = {'Good': '#4CAF50', 'Neutral': '#FFA500', 'Bad': '#FF5252'}

        # Main metrics
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"### 🔮 Predicted Next Trade Outcome")
            st.markdown(f"""
            <div class="section-animation" style="text-align: center; padding: 25px;
                        background-color: {prediction_colors[prediction]}10;
                        border: 2px solid {prediction_colors[prediction]};
                        border-radius: 10px;">
                <h1 style="color: {prediction_colors[prediction]}; margin: 0; transform: scale(1);">
                    {prediction} {['🎉', '⚡', '🔥'][['Good', 'Neutral', 'Bad'].index(prediction)]}
                </h1>
                <p style="color: {prediction_colors[prediction]};">Confidence: {confidence * 100:.0f}%</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"### 📊 Performance Overview")
            st.markdown(f"""
            <div class="section-animation" style="padding: 20px; border-radius: 10px; 
                        background-color: {st.get_option("theme.backgroundColor")};
                        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                    <div>
                        <h3 style="color: #4CAF50;">🔥 Win Streak</h3>
                        <h1 style="text-align: center;">{last_row['Winning Streak']}</h1>
                    </div>
                    <div>
                        <h3 style="color: #FF5252;">💔 Loss Streak</h3>
                        <h1 style="text-align: center;">{last_row['Losing Streak']}</h1>
                    </div>
                    <div>
                        <h3 style="color: #2196F3;">🎯 Win Rate</h3>
                        <h1 style="text-align: center;">{last_row['WinRate']:.1f}%</h1>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Dynamic Caution Box
        caution_styles = {
            'Good': {'bg': '#E8F5E9', 'border': '#4CAF50', 'text': '#2E7D32'},
            'Neutral': {'bg': '#FFF3E0', 'border': '#FFA726', 'text': '#EF6C00'},
            'Bad': {'bg': '#FFEBEE', 'border': '#EF5350', 'text': '#C62828'}
        }

        st.markdown(f"""
        <div style="padding: 15px; margin-top: 20px;
                    background-color: {caution_styles[prediction]['bg']}; 
                    border-radius: 10px;
                    border-left: 5px solid {caution_styles[prediction]['border']};">
            <h3 style="color: {caution_styles[prediction]['text']}; margin-top: 0;">
                {['⚠️', '🔔', '⚠️'][['Bad', 'Neutral', 'Good'].index(prediction)]} Trading Recommendations
            </h3>
            <ul style="color: {caution_styles[prediction]['text']};">
                <li>Moderate position sizing</li>
                <li>Confirm with technical analysis</li>
                <li>Monitor key support/resistance</li>
                <li>Review recent trade patterns</li>
                <li>Consider {prediction}-specific strategies</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Historical Performance Chart
        st.markdown("---")
        st.markdown("### 📈 Historical Win Rate")
        chart_data = st.session_state.trades[['WinRate']].rename(columns={'WinRate': 'Win Rate (%)'})
        st.line_chart(chart_data, use_container_width=True)

    else:
        st.info("No trades recorded yet. Make your first trade above!")

    # Animated Separator
    st.markdown("""
    <div style="height: 2px; 
                background: linear-gradient(90deg, transparent 0%, #4CAF50 50%, transparent 100%); 
                margin: 2rem 0; 
                animation: separatorAnim 2s infinite;"></div>
    """, unsafe_allow_html=True)

    # --- Trading Journal ---
    st.markdown("---")
    st.subheader("📒 Trading Journal")
    if not st.session_state.trades.empty:
        # Custom CSS injection
        st.markdown(f"""
        <style>
            div[data-testid="stDataFrame"] {{
                background-color: {st.get_option("theme.backgroundColor")} !important;
            }}
            div[data-testid="stDataFrame"] div[data-testid="stDataFrameContainer"] {{
                background-color: {st.get_option("theme.backgroundColor")} !important;
            }}
            div[data-testid="stDataFrame"] table {{
                background-color: {st.get_option("theme.backgroundColor")} !important;
            }}
            div[data-testid="stDataFrame"] th, 
            div[data-testid="stDataFrame"] td {{
                background-color: {st.get_option("theme.backgroundColor")} !important;
            }}
        </style>
        """, unsafe_allow_html=True)

        styled_df = st.session_state.trades.tail(10).sort_index(ascending=False).style \
            .applymap(
            lambda x: 'color: #4CAF50' if x == 'Good' else ('color: #FF5252' if x == 'Bad' else 'color: #FFA726'),
            subset=['Trading State']) \
            .format({'WinRate': '{:.1f}%'})

        st.dataframe(styled_df, use_container_width=True)
    else:
        st.info("No trades recorded yet. Make your first trade above!")


if __name__ == "__main__":
    main()