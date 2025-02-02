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
        # Load credentials from Streamlit Secrets
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


def calculate_win_rate(df, window=6):
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

    last_row = df.iloc[-1]
    losing_condition = last_row['Losing Streak'] >= 2 or last_row['WinRate'] < 45
    winning_condition = last_row['Winning Streak'] >= 2 and last_row['WinRate'] > 55

    if losing_condition:
        return 'Bad', 0.95
    elif winning_condition:
        return 'Good', 0.90
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
                st.rerun()

    # --- Dashboard ---
    if not st.session_state.trades.empty:
        latest = st.session_state.trades.iloc[-1]
        prediction, confidence = predict_state(st.session_state.trades)

        # Prediction Display
        prediction_color = {
            'Good': ('#4CAF50', '🎉'),
            'Neutral': ('#FFA500', '⚡'),
            'Bad': ('#FF5252', '🔥')
        }[prediction]

        st.markdown(f"""
        <div style="border-radius: 10px;
                    padding: 25px;
                    margin: 15px 0;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
                    border-left: 5px solid {prediction_color[0]};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="color: {prediction_color[0]}; margin: 0;">
                        {prediction} {prediction_color[1]}
                    </h2>
                    <p>Confidence Level: {confidence * 100:.0f}%</p>
                </div>
                <div style="text-align: right;">
                    <h3>Current Streaks</h3>
                    <p>🔥 Wins: {latest['Winning Streak']} &nbsp; 💔 Losses: {latest['Losing Streak']}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Current Win Rate", f"{latest['WinRate']:.1f}%")
        with col2:
            st.metric("Total Trades", len(st.session_state.trades))
        with col3:
            st.metric("Total Gain/Loss", f"${st.session_state.trades['Gain'].sum():.2f}")

        # Historical Data
        st.subheader("📒 Trading Journal")
        display_df = st.session_state.trades.copy()
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d %H:%M')

        if 'Trading State' in display_df.columns:
            styled_df = display_df.style.applymap(
                lambda x: 'color: #4CAF50' if x == 'Good' else
                ('color: #FF5252' if x == 'Bad' else 'color: #FFA500'),
                subset=['Trading State']
            )
        else:
            styled_df = display_df.style

        styled_df = styled_df.format({
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