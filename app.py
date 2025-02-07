import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import calendar
import streamlit as st
from streamlit.components.v1 import html
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Google Sheets Integration ---
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SPREADSHEET_NAME = "TradingHistory"


def get_gsheet_client():
    try:
        creds_dict = {
            "type": "service_account",
            "project_id": st.secrets["google_credentials"]["project_id"],
            "private_key_id": st.secrets["google_credentials"]["private_key_id"],
            "private_key": st.secrets["google_credentials"]["private_key"].replace('\\n', '\n'),
            "client_email": st.secrets["google_credentials"]["client_email"],
            "client_id": st.secrets["google_credentials"]["client_id"],
            "auth_uri": st.secrets["google_credentials"]["auth_uri"],
            "token_uri": st.secrets["google_credentials"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["google_credentials"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["google_credentials"]["client_x509_cert_url"],
            "universe_domain": st.secrets["google_credentials"]["universe_domain"]
        }
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Google Sheets connection error: {str(e)}")
        return None


def save_trade_to_sheet(trade_data):
    client = get_gsheet_client()
    if client:
        try:
            sheet = client.open(SPREADSHEET_NAME).sheet1
            sheet.append_row(trade_data)
        except Exception as e:
            st.error(f"Failed to save trade: {str(e)}")


def load_trade_history_from_sheet():
    try:
        client = get_gsheet_client()
        if not client:
            return pd.DataFrame()

        sheet = client.open(SPREADSHEET_NAME).sheet1
        data = sheet.get_all_records()

        required_columns = {
            'Date': pd.NaT,
            'Win/Lose': 0,
            'Gain': 0.0,
            'Winning Streak': 0,
            'Losing Streak': 0,
            'WinRate': 0.0,
            'Trading State': 'Neutral'
        }

        df = pd.DataFrame(data).rename(columns={
            'Gains': 'Gain',
            'Winning Streaks': 'Winning Streak',
            'LoosingStreaks': 'Losing Streak',
            'Loosing Streak': 'Losing Streak'
        })

        for col, default in required_columns.items():
            if col not in df.columns:
                df[col] = default

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Win/Lose'] = df['Win/Lose'].astype(int)
        df['Trading State'] = df['Trading State'].fillna('Neutral')

        return df
    except Exception as e:
        st.error(f"Error loading trade history: {str(e)}")
        return pd.DataFrame()


# --- Core Logic ---
def calculate_streaks(df):
    if df.empty:
        return df

    df['Win/Lose'] = df['Win/Lose'].astype(int)
    current_win, current_loss = 0, 0
    win_streaks, loss_streaks = [], []

    for outcome in df['Win/Lose']:
        if outcome == 1:
            current_win += 1
            current_loss = 0
        else:
            current_loss += 1
            current_win = 0
        win_streaks.append(current_win)
        loss_streaks.append(current_loss)

    df['Winning Streak'] = win_streaks
    df['Losing Streak'] = loss_streaks
    return df


def calculate_win_rate(df, window=5):  # Now using 5-trade window
    if df.empty:
        return df

    df['WinRate'] = (df['Win/Lose']
                     .rolling(window, min_periods=1)
                     .mean()
                     .fillna(0.5) * 100)
    return df


def predict_state(df):
    if df.empty:
        return 'Neutral', 0.65

    # Strictly consider last 5 trades
    last_5 = df['Win/Lose'].tail(5)
    if len(last_5) < 5:
        return 'Neutral', 0.65

    win_rate = last_5.mean() * 100

    if win_rate > 50:
        return 'Good', 0.90
    elif win_rate < 50:
        return 'Bad', 0.95
    return 'Neutral', 0.65


# --- Calendar Visualization ---
def create_trade_calendar(df, selected_date):
    df['Date'] = pd.to_datetime(df['Date'])
    daily_trades = df.groupby(df['Date'].dt.date).agg(
        Total_Trades=('Win/Lose', 'count'),
        Net_Wins=('Win/Lose', 'sum')
    ).reset_index()

    month = selected_date.month
    year = selected_date.year

    st.subheader(f"🗓 Trading Calendar - {selected_date.strftime('%B %Y')}")

    # Month navigation
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("← Previous Month"):
            selected_date = selected_date - timedelta(days=selected_date.day)
            st.session_state.calendar_date = selected_date
    with col5:
        if st.button("Next Month →"):
            next_month = selected_date.replace(day=28) + timedelta(days=4)
            selected_date = next_month - timedelta(days=next_month.day)
            st.session_state.calendar_date = selected_date

    # Calendar grid
    cal = calendar.Calendar()
    weeks = cal.monthdayscalendar(year, month)
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    # Header
    cols = st.columns(7)
    for i, day in enumerate(day_names):
        cols[i].markdown(f"**{day}**", unsafe_allow_html=True)

    # Body
    for week in weeks:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write(" ")
                continue

            current_date = datetime(year, month, day).date()
            daily_data = daily_trades[daily_trades['Date'] == current_date]

            if not daily_data.empty:
                total = daily_data['Total_Trades'].values[0]
                wins = daily_data['Net_Wins'].values[0]
                losses = total - wins

                color = "#4CAF50" if wins > losses else "#FF5252" if losses > wins else "#FFA500"
                html_content = f"""
                <div style="border: 1px solid #e0e0e0; 
                            border-radius: 5px; 
                            padding: 5px; 
                            text-align: center;
                            background-color: {color}30;
                            min-height: 80px;
                            transition: all 0.2s ease;">
                    <div style="font-weight: bold; color: {color};">{day}</div>
                    <div style="font-size: 0.8em;">
                        <span style="color: #4CAF50;">▲{wins}</span>
                        <span style="color: #FF5252;">▼{losses}</span>
                    </div>
                </div>
                """
                cols[i].markdown(html_content, unsafe_allow_html=True)
            else:
                cols[i].markdown(f"""
                <div style="color: #666; 
                            text-align: center; 
                            padding: 5px;
                            min-height: 80px;">
                    {day}
                </div>
                """, unsafe_allow_html=True)


# --- Main App ---
def main():
    st.set_page_config(page_title="Trading Assistant", layout="wide")

    # Initialize session states
    if 'calendar_date' not in st.session_state:
        st.session_state.calendar_date = datetime.now().date()

    if 'trades' not in st.session_state:
        df = load_trade_history_from_sheet()
        if not df.empty:
            df = calculate_streaks(calculate_win_rate(df))
        else:
            df = pd.DataFrame(columns=[
                'Date', 'Win/Lose', 'Gain',
                'Winning Streak', 'Losing Streak',
                'WinRate', 'Trading State'
            ])
        st.session_state.trades = df

    # --- Trade Input Form ---
    with st.expander("➕ New Trade Entry", expanded=True):
        with st.form("trade_form"):
            col1, col2 = st.columns(2)
            with col1:
                win_lose = st.radio("Outcome", [1, 0],
                                    format_func=lambda x: "Win 🎉" if x else "Lose 💔")
            with col2:
                gain = st.number_input("Gain/Loss ($)", value=0.0, step=0.01)

            if st.form_submit_button("💾 Save Trade"):
                new_trade = {
                    'Date': datetime.now(),
                    'Win/Lose': win_lose,
                    'Gain': gain,
                    'Winning Streak': 0,
                    'Losing Streak': 0,
                    'WinRate': 0.0,
                    'Trading State': 'Neutral'
                }

                updated_df = pd.concat([
                    st.session_state.trades,
                    pd.DataFrame([new_trade])
                ], ignore_index=True)

                updated_df = calculate_streaks(calculate_win_rate(updated_df))
                prediction, _ = predict_state(updated_df)
                updated_df.at[updated_df.index[-1], 'Trading State'] = prediction

                # Prepare data for Google Sheets
                new_row = updated_df.iloc[-1]
                trade_data = [
                    new_row['Date'].strftime('%Y-%m-%d %H:%M:%S'),
                    int(new_row['Win/Lose']),
                    float(new_row['Gain']),
                    int(new_row['Winning Streak']),
                    int(new_row['Losing Streak']),
                    float(new_row['WinRate']),
                    str(new_row['Trading State'])
                ]

                st.session_state.trades = updated_df
                save_trade_to_sheet(trade_data)
                st.balloons()
                st.rerun()

    # --- Dashboard ---
    if not st.session_state.trades.empty:
        latest = st.session_state.trades.iloc[-1]
        prediction, confidence = predict_state(st.session_state.trades)

        # Prediction Display
        prediction_color = {
            'Good': ('#4CAF50', '🚀', 'Great Job! Keep it up!'),
            'Neutral': ('#FFA500', '⚡', 'Stay Alert!'),
            'Bad': ('#FF5252', '⚠️', 'Review Your Strategy!')
        }[prediction]

        confidence_percent = confidence * 100

        st.markdown(f"""
        <div style="background-color: {prediction_color[0]}20;
                    padding: 20px;
                    border-radius: 10px;
                    border-left: 5px solid {prediction_color[0]};
                    margin: 10px 0;">
            <div style="display: flex; align-items: center;">
                <div style="font-size: 40px; margin-right: 20px;">
                    {prediction_color[1]}
                </div>
                <div>
                    <h2 style="color: {prediction_color[0]}; margin: 0;">
                        {prediction} State - {prediction_color[2]}
                    </h2>
                    <p style="margin: 5px 0;">Confidence Level: {confidence_percent:.0f}%</p>
                    <div style="background-color: #e0e0e0; border-radius: 5px; height: 10px;">
                        <div style="background-color: {prediction_color[0]}; 
                                    width: {confidence_percent}%; 
                                    height: 10px; 
                                    border-radius: 5px;">
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics
        cols = st.columns(4)
        with cols[0]:
            st.markdown("### 📊 Current Win Rate")
            st.markdown(f"<h1 style='color: #4CAF50; text-align: center;'>{latest['WinRate']:.1f}%</h1>",
                        unsafe_allow_html=True)
        with cols[1]:
            st.markdown("### 🔥 Winning Streak")
            st.markdown(f"<h1 style='color: #4CAF50; text-align: center;'>{latest['Winning Streak']}</h1>",
                        unsafe_allow_html=True)
        with cols[2]:
            st.markdown("### 💔 Losing Streak")
            st.markdown(f"<h1 style='color: #FF5252; text-align: center;'>{latest['Losing Streak']}</h1>",
                        unsafe_allow_html=True)
        with cols[3]:
            st.markdown("### 💰 Total Gain/Loss")
            total_gain = st.session_state.trades['Gain'].sum()
            color = "#4CAF50" if total_gain >= 0 else "#FF5252"
            st.markdown(f"<h1 style='color: {color}; text-align: center;'>${total_gain:.2f}</h1>",
                        unsafe_allow_html=True)

        # Historical Data
        st.subheader("📒 Trading Journal")
        display_df = st.session_state.trades.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d %H:%M')

        styled_df = display_df.style.apply(
            lambda x: [f'background-color: #4CAF5020' if x['Trading State'] == 'Good' else
                       f'background-color: #FF525220' if x['Trading State'] == 'Bad' else
                       f'background-color: #FFA50020' for _ in x],
            axis=1
        ).format({
            'Gain': '${:.2f}',
            'WinRate': '{:.1f}%'
        })

        st.dataframe(styled_df, use_container_width=True, height=400)

        # Win Rate Chart
        st.subheader("📈 Win Rate Trend")
        st.line_chart(st.session_state.trades.set_index('Date')['WinRate'])

    else:
        st.info("🌟 No trades recorded yet. Make your first trade above!")

    # --- Trading Calendar ---
    st.markdown("---")
    create_trade_calendar(st.session_state.trades, st.session_state.calendar_date)


if __name__ == "__main__":
    main()