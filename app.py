import streamlit as st
import yfinance as yf
import json
import os
import pandas as pd
from datetime import datetime
import plotly.express as px

PORTFOLIO_FILE = "portfolio_data.json"
NET_VALUE_FILE = "net_value_history.json"
REALIZED_PROFIT_FILE = "realized_profit.json"

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return [] if file_path.endswith(".json") else {}

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def load_portfolio():
    return load_json(PORTFOLIO_FILE)

def save_portfolio(pf):
    save_json(PORTFOLIO_FILE, pf)

def load_realized_profit():
    return load_json(REALIZED_PROFIT_FILE)

def save_realized_profit(data):
    save_json(REALIZED_PROFIT_FILE, data)

def fetch_price(symbol):
    try:
        return yf.Ticker(symbol).history(period="1d")["Close"].iloc[-1]
    except:
        return None

def calculate_value(pf):
    result = []
    total = 0.0
    price_cache = {}
    for symbol, data in pf.items():
        shares = data["shares"]
        cost = data["cost"]
        if symbol == "CASH":
            price = 1.0
        elif shares < 0:
            price = cost  # 當作賣出價格
        else:
            price = fetch_price(symbol)
            price_cache[symbol] = price
        if price is not None:
            value = price * shares
            cost_total = cost * shares
            profit_rate = ((value - cost_total) / cost_total * 100) if cost_total != 0 else 0
            total += value
            row = {
                "股票代碼": symbol,
                "股數": shares,
                "現價": round(price, 2),
                "成本價": cost,
                "現值": round(value, 2),
                "成本總額": round(cost_total, 2)
            }
            if symbol != "CASH":
                row["報酬率"] = f"{profit_rate:.2f}%"
            result.append(row)
        else:
            row = {
                "股票代碼": symbol,
                "股數": shares,
                "現價": "錯誤",
                "成本價": cost,
                "現值": "錯誤",
                "成本總額": cost * shares
            }
            if symbol != "CASH":
                row["報酬率"] = "N/A"
            result.append(row)
    return pd.DataFrame(result), round(total, 2), price_cache

def save_net_value_history(latest_value):
    history = load_json(NET_VALUE_FILE)
    today = datetime.now().date().strftime("%Y-%m-%d")
    history = [h for h in history if h["date"] != today]
    history.append({"date": today, "value": latest_value})
    history = sorted(history, key=lambda x: x["date"])
    save_json(NET_VALUE_FILE, history)

def load_net_value_history():
    return load_json(NET_VALUE_FILE)

def draw_pie_chart(df):
    if not df.empty:
        df = df[df["股票代碼"] != "CASH"]
        df["現值"] = pd.to_numeric(df["現值"], errors="coerce")
        df = df.sort_values("現值", ascending=False)
        top_df = df.head(5)
        others_value = df["現值"].iloc[5:].sum()
        if others_value > 0:
            others_row = pd.DataFrame([{"股票代碼": "其他", "現值": others_value}])
            top_df = pd.concat([top_df, others_row], ignore_index=True)
        fig = px.pie(top_df, names="股票代碼", values="現值", title="前五大持股比例")
        st.plotly_chart(fig, use_container_width=True)

st.set_page_config(page_title="資產管理器", layout="wide")
st.title("📊 我的資產管理器")

portfolio = load_portfolio()
realized_profit = load_realized_profit()

col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.text_input("股票代碼", placeholder="例如 AAPL").upper()
with col2:
    shares = st.number_input("持股數量（買入為正，賣出為負）", value=1, step=1)
with col3:
    cost = st.number_input("每股成本（買入時）或賣出價格（賣出時）", min_value=0.0, step=0.1)

if st.button("新增 / 賣出", key="trade", help="點擊送出交易", type="secondary"):
    if symbol:
        if "CASH" not in portfolio:
            portfolio["CASH"] = {"shares": 0.0, "cost": 1.0}

        if symbol in portfolio:
            old_shares = portfolio[symbol]["shares"]
            old_cost = portfolio[symbol]["cost"]
            if shares > 0:
                total_cost = cost * shares
                if portfolio["CASH"]["shares"] < total_cost:
                    st.error("💸 現金餘額不足，無法完成此次買入。")
                else:
                    new_shares = old_shares + shares
                    new_cost = ((old_cost * old_shares + cost * shares) / new_shares)
                    portfolio[symbol]["cost"] = round(new_cost, 2)
                    portfolio[symbol]["shares"] = new_shares
                    portfolio["CASH"]["shares"] -= total_cost
            else:
                sell_shares = min(-shares, old_shares)
                price = 1.0 if symbol == "CASH" else fetch_price(symbol)
                proceeds = price * sell_shares * (1 - 0.001)
                realized_profit.append({
                    "股票代碼": symbol,
                    "賣出價格": round(price, 2),
                    "成本價": old_cost,
                    "數量": sell_shares,
                    "實現損益": round((price - old_cost) * sell_shares * (1 - 0.001), 2),
                    "日期": datetime.now().strftime("%Y-%m-%d")
                })
                portfolio[symbol]["shares"] -= sell_shares
                portfolio["CASH"]["shares"] += proceeds
        else:
            total_cost = cost * shares
            if portfolio["CASH"]["shares"] < total_cost:
                st.error("💸 現金餘額不足，無法完成此次買入。")
            else:
                portfolio[symbol] = {"shares": shares, "cost": cost}
                portfolio["CASH"]["shares"] -= total_cost

        if symbol in portfolio and portfolio[symbol]["shares"] <= 0:
            del portfolio[symbol]
            st.success(f"🗑 已清空持股 {symbol}")
        elif symbol in portfolio:
            price = 1.0 if symbol == "CASH" else fetch_price(symbol)
            shares_now = portfolio[symbol]["shares"]
            avg_cost = portfolio[symbol]["cost"]
            value = price * shares_now
            profit_rate = ((value - avg_cost * shares_now) / (avg_cost * shares_now) * 100) if avg_cost * shares_now else 0
            st.success(f"✅ {symbol} 持股 {shares_now} 股，平均成本 ${avg_cost:.2f}，報酬率 {profit_rate:.2f}%")

        save_portfolio(portfolio)
        save_realized_profit(realized_profit)
        st.rerun()

with st.expander("💵 管理現金部位"):
    current_cash = round(portfolio.get("CASH", {}).get("shares", 0), 2)
    st.write(f"目前現金餘額：${current_cash:,.2f}")

    add_cash = st.number_input("➕ 增加現金金額", min_value=0.0, step=100.0)
    sub_cash = st.number_input("➖ 減少現金金額", min_value=0.0, step=100.0)

    if st.button("更新現金餘額"):
        new_cash = current_cash + add_cash - sub_cash
        portfolio["CASH"] = {"shares": new_cash, "cost": 1.0}
        save_portfolio(portfolio)
        st.success(f"已更新現金部位為 ${new_cash:,.2f}")
        st.rerun()

st.subheader("📋 投資組合總覽")
df, total_value, _ = calculate_value(portfolio)
if not df.empty:
    selected_symbols = st.multiselect("選擇欲刪除的股票持倉：", [row["股票代碼"] for _, row in df.iterrows() if row["股票代碼"] != "CASH"])
    if selected_symbols:
        if st.button("🗑 確認刪除選取項目"):
            for symbol in selected_symbols:
                if symbol in portfolio:
                    del portfolio[symbol]
            save_portfolio(portfolio)
            st.success("✅ 已刪除所選股票")
            st.rerun()
    st.dataframe(df, use_container_width=True)
    draw_pie_chart(df)

st.markdown(f"### 💰 總資產淨值：<span style='color:#00ff88'> $ {total_value:,.2f} </span>", unsafe_allow_html=True)
save_net_value_history(total_value)

st.subheader("📈 淨值歷史變化圖")
history = load_net_value_history()
if len(history) > 1:
    hist_df = pd.DataFrame(history)
    hist_df["date"] = pd.to_datetime(hist_df["date"])
    hist_df = hist_df.drop_duplicates(subset="date")
    hist_df = hist_df.sort_values("date")
    hist_df["date_str"] = hist_df["date"].dt.strftime("%Y/%m/%d")
    fig = px.line(hist_df, x="date_str", y="value", markers=True, title="Net Asset Value (Daily)")
    fig.update_layout(
        plot_bgcolor="#2e2e2e",
        paper_bgcolor="#2e2e2e",
        font_color="white",
        xaxis_title="日期",
        yaxis_title="USD",
        hovermode="x unified",
        xaxis=dict(
            type="category",
            showticklabels=True,
            rangeslider=dict(visible=True),
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="1w", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(step="all")
                ])
            )
        )
    )
    fig.update_traces(marker=dict(size=6, color="#00ccff"), line=dict(color="#00ccff"))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("⚠️ 尚未累積足夠資料繪製折線圖。")

st.subheader("💼 已實現損益紀錄")
realized_df = pd.DataFrame(realized_profit)
if not realized_df.empty:
    realized_df["index"] = realized_df.index.astype(str)
    selected_rows = st.multiselect("選擇欲刪除的損益紀錄：", realized_df["index"], format_func=lambda x: f"{realized_df.loc[int(x), '日期']} - {realized_df.loc[int(x), '股票代碼']} ({realized_df.loc[int(x), '數量']} 股) 損益 ${realized_df.loc[int(x), '實現損益']}")
    if selected_rows:
        if st.button("🗑 確認刪除所選損益紀錄"):
            for idx in sorted([int(i) for i in selected_rows], reverse=True):
                profit_entry = realized_profit[idx]
                portfolio["CASH"]["shares"] -= profit_entry.get("實現損益", 0)
                symbol = profit_entry.get("股票代碼")
                qty = profit_entry.get("數量", 0)
                cost = profit_entry.get("成本價", 0)
                if symbol:
                    if symbol in portfolio:
                        portfolio[symbol]["shares"] += qty
                    else:
                        portfolio[symbol] = {"shares": qty, "cost": cost}
                realized_profit.pop(idx)
            save_realized_profit(realized_profit)
            save_portfolio(portfolio)
            st.success("✅ 已刪除所選損益紀錄")
            st.rerun()
    st.dataframe(realized_df.drop(columns="index"), use_container_width=True)
else:
    st.info("尚無已實現損益資料。")
