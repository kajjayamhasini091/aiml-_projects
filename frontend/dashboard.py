"""
Streamlit Dashboard for the Razorpay AI Finance Controller.

Provides an interactive UI for uploading CSVs, running reconciliation,
viewing results, and inspecting audit logs.

Usage:
    streamlit run frontend/dashboard.py
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Razorpay AI Finance Controller",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000/api"

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Razorpay brand colors */
    :root {
        --rz-primary: #072654;
        --rz-accent: #2D7FF9;
        --rz-success: #1CAC78;
        --rz-warning: #F5A623;
        --rz-error: #E74C3C;
    }

    .main-header {
        background: linear-gradient(135deg, #072654 0%, #2D7FF9 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        color: white;
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: rgba(255,255,255,0.85);
        margin: 0.3rem 0 0 0;
        font-size: 0.95rem;
    }

    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1.2rem;
        border-left: 4px solid;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; color: #666; }
    .metric-card .value { font-size: 2rem; font-weight: 700; margin: 0.3rem 0; }

    .status-matched { color: #1CAC78; }
    .status-mismatch { color: #E74C3C; }
    .status-unmatched { color: #F5A623; }
    .status-ai_matched { color: #2D7FF9; }
    .status-ai_flagged { color: #E67E22; }
    .status-pending { color: #9B59B6; }

    div[data-testid="stSidebar"] {
        background: #072654;
    }
    div[data-testid="stSidebar"] .stRadio label {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper Functions ─────────────────────────────────────────────────

def api_call(endpoint, method="GET", files=None, params=None):
    """Make an API call with error handling."""
    try:
        url = f"{API_BASE}/{endpoint}"
        if method == "GET":
            resp = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            resp = requests.post(url, files=files, timeout=30)
        resp.raise_for_status()
        return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
    except requests.ConnectionError:
        st.error("⚠️ Cannot connect to API. Make sure the backend is running: `uvicorn app.main:app --port 8000`")
        return None
    except requests.HTTPError as e:
        st.error(f"API Error: {e}")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def status_color(status):
    """Return a color for each reconciliation status."""
    colors = {
        "MATCHED": "#1CAC78",
        "MISMATCH": "#E74C3C",
        "UNMATCHED": "#F5A623",
        "PENDING_AI_REVIEW": "#9B59B6",
        "AI_MATCHED": "#2D7FF9",
        "AI_FLAGGED": "#E67E22",
    }
    return colors.get(status, "#666")


def status_emoji(status):
    """Return an emoji for each status."""
    emojis = {
        "MATCHED": "✅",
        "MISMATCH": "❌",
        "UNMATCHED": "⚠️",
        "PENDING_AI_REVIEW": "🔍",
        "AI_MATCHED": "🤖",
        "AI_FLAGGED": "🚩",
    }
    return emojis.get(status, "❓")


# ── Header ───────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>💰 Razorpay AI Finance Controller</h1>
    <p>Intelligent financial reconciliation powered by deterministic rules + AI reasoning</p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar Navigation ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧭 Navigation")
    page = st.radio(
        "Select Page",
        ["📤 Upload Data", "📊 Dashboard", "🔍 Transaction Explorer", "📋 Audit Log"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**Razorpay AI Buildathon 2026**")
    st.caption("AI Finance Controller Track")


# ══════════════════════════════════════════════════════════════════════
# PAGE 1: Upload Data
# ══════════════════════════════════════════════════════════════════════

if page == "📤 Upload Data":
    st.header("📤 Upload Financial Data")
    st.markdown("Upload CSV files for each data source, then run reconciliation.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💳 Payments")
        payments_file = st.file_uploader("Upload payments.csv", type=["csv"], key="payments")
        if payments_file:
            result = api_call("upload/payments", method="POST", files={"file": payments_file})
            if result:
                st.success(f"✅ {result['message']}")

        st.subheader("🏦 Bank Statement")
        bank_file = st.file_uploader("Upload bank_statement.csv", type=["csv"], key="bank")
        if bank_file:
            result = api_call("upload/bank_statement", method="POST", files={"file": bank_file})
            if result:
                st.success(f"✅ {result['message']}")

    with col2:
        st.subheader("📦 Settlements")
        settlements_file = st.file_uploader("Upload settlements.csv", type=["csv"], key="settlements")
        if settlements_file:
            result = api_call("upload/settlements", method="POST", files={"file": settlements_file})
            if result:
                st.success(f"✅ {result['message']}")

        st.subheader("↩️ Refunds")
        refunds_file = st.file_uploader("Upload refunds.csv", type=["csv"], key="refunds")
        if refunds_file:
            result = api_call("upload/refunds", method="POST", files={"file": refunds_file})
            if result:
                st.success(f"✅ {result['message']}")

    st.markdown("---")

    # Run Reconciliation Button
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("🚀 Run Reconciliation", type="primary", use_container_width=True):
            with st.spinner("Running reconciliation pipeline..."):
                result = api_call("reconcile", method="POST")
                if result:
                    st.success(f"✅ {result['message']}")
                    stats = result.get("stats", {})
                    st.markdown("### Results Summary")
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Total", stats.get("total_records", 0))
                    mc2.metric("Matched", stats.get("matched", 0))
                    mc3.metric("Mismatched", stats.get("mismatched", 0))
                    mc4.metric("AI Processed", stats.get("ai_matched", 0) + stats.get("ai_flagged", 0))

    with col_info:
        st.info("💡 Upload all 4 CSV files first, then click **Run Reconciliation** to process them.")


# ══════════════════════════════════════════════════════════════════════
# PAGE 2: Dashboard
# ══════════════════════════════════════════════════════════════════════

elif page == "📊 Dashboard":
    st.header("📊 Reconciliation Dashboard")

    stats = api_call("stats")

    if stats and stats.get("total_records", 0) > 0:
        # ── Metric Cards ────────────────────────────────────────
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📋 Total Records", stats["total_records"])
        c2.metric("✅ Matched", stats["matched"], delta=None)
        c3.metric("❌ Mismatched", stats["mismatched"], delta=None)
        c4.metric("⚠️ Unmatched", stats["unmatched"], delta=None)
        c5.metric("🤖 AI Processed", stats["ai_matched"] + stats["ai_flagged"])

        # ── Match Rate ──────────────────────────────────────────
        st.markdown("---")
        rate_col, chart_col = st.columns([1, 2])

        with rate_col:
            st.markdown("### Match Rate")
            match_rate = stats["match_rate_percent"]
            st.markdown(
                f"<h1 style='color: {'#1CAC78' if match_rate >= 70 else '#F5A623' if match_rate >= 50 else '#E74C3C'}; "
                f"font-size: 3.5rem; margin: 0;'>{match_rate}%</h1>",
                unsafe_allow_html=True,
            )
            st.progress(match_rate / 100)

            # Method breakdown
            results = api_call("results") or []
            deterministic = sum(1 for r in results if r.get("method") == "deterministic")
            ai = sum(1 for r in results if r.get("method") == "ai")
            st.markdown("**Resolution Method**")
            st.markdown(f"- 🔧 Deterministic: **{deterministic}**")
            st.markdown(f"- 🤖 AI Reasoning: **{ai}**")

        with chart_col:
            # Status distribution pie chart
            status_data = {
                "MATCHED": stats["matched"],
                "MISMATCH": stats["mismatched"],
                "UNMATCHED": stats["unmatched"],
                "PENDING_AI_REVIEW": stats["pending_ai_review"],
                "AI_MATCHED": stats["ai_matched"],
                "AI_FLAGGED": stats["ai_flagged"],
            }
            # Filter out zero values
            status_data = {k: v for k, v in status_data.items() if v > 0}

            if status_data:
                fig = px.pie(
                    names=list(status_data.keys()),
                    values=list(status_data.values()),
                    color=list(status_data.keys()),
                    color_discrete_map={
                        "MATCHED": "#1CAC78",
                        "MISMATCH": "#E74C3C",
                        "UNMATCHED": "#F5A623",
                        "PENDING_AI_REVIEW": "#9B59B6",
                        "AI_MATCHED": "#2D7FF9",
                        "AI_FLAGGED": "#E67E22",
                    },
                    title="Status Distribution",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(showlegend=True, height=350)
                st.plotly_chart(fig, use_container_width=True)

        # ── Mismatch Breakdown Bar Chart ─────────────────────────
        results = api_call("results") or []
        mismatch_types = {}
        for r in results:
            mt = r.get("mismatch_type")
            if mt:
                mismatch_types[mt] = mismatch_types.get(mt, 0) + 1

        if mismatch_types:
            st.markdown("### Mismatch Breakdown by Type")
            fig2 = px.bar(
                x=list(mismatch_types.keys()),
                y=list(mismatch_types.values()),
                color=list(mismatch_types.keys()),
                color_discrete_sequence=["#E74C3C", "#F5A623", "#9B59B6", "#E67E22", "#3498DB"],
                labels={"x": "Mismatch Type", "y": "Count"},
            )
            fig2.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("📭 No reconciliation data yet. Go to **Upload Data** to get started.")


# ══════════════════════════════════════════════════════════════════════
# PAGE 3: Transaction Explorer
# ══════════════════════════════════════════════════════════════════════

elif page == "🔍 Transaction Explorer":
    st.header("🔍 Transaction Explorer")

    # Filters
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        status_filter = st.selectbox(
            "Status",
            ["All", "MATCHED", "MISMATCH", "UNMATCHED", "PENDING_AI_REVIEW", "AI_MATCHED", "AI_FLAGGED"],
        )
    with filter_col2:
        type_filter = st.selectbox("Record Type", ["All", "payment", "settlement", "refund"])
    with filter_col3:
        method_filter = st.selectbox("Method", ["All", "deterministic", "ai"])

    # Build query params
    params = {}
    if status_filter != "All":
        params["status"] = status_filter
    if type_filter != "All":
        params["record_type"] = type_filter
    if method_filter != "All":
        params["method"] = method_filter

    results = api_call("results", params=params)

    if results:
        # Build dataframe
        df = pd.DataFrame(results)
        display_cols = ["record_type", "record_id", "status", "matched_with_type", "matched_with_id", "method", "confidence", "mismatch_type"]
        available_cols = [c for c in display_cols if c in df.columns]

        st.markdown(f"**{len(df)} records found**")

        # Color-coded status column
        def highlight_status(row):
            color_map = {
                "MATCHED": "background-color: #d4edda",
                "MISMATCH": "background-color: #f8d7da",
                "UNMATCHED": "background-color: #fff3cd",
                "PENDING_AI_REVIEW": "background-color: #e8daef",
                "AI_MATCHED": "background-color: #d6eaf8",
                "AI_FLAGGED": "background-color: #fdebd0",
            }
            return [color_map.get(row["status"], "") for _ in row]

        styled_df = df[available_cols].style.apply(highlight_status, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=400)

        # Detail view
        st.markdown("---")
        st.subheader("📝 Record Detail")
        record_ids = df["record_id"].tolist()
        selected_id = st.selectbox("Select a record to inspect:", record_ids)

        if selected_id:
            detail = api_call(f"results/{selected_id}")
            if detail:
                d1, d2 = st.columns(2)
                with d1:
                    st.markdown(f"**Record Type:** `{detail['record_type']}`")
                    st.markdown(f"**Record ID:** `{detail['record_id']}`")
                    st.markdown(f"**Status:** {status_emoji(detail['status'])} `{detail['status']}`")
                    st.markdown(f"**Method:** `{detail['method']}`")
                with d2:
                    st.markdown(f"**Matched With:** `{detail.get('matched_with_type', 'N/A')}` → `{detail.get('matched_with_id', 'N/A')}`")
                    st.markdown(f"**Mismatch Type:** `{detail.get('mismatch_type', 'None')}`")
                    if detail.get("confidence") is not None:
                        st.markdown(f"**AI Confidence:** {detail['confidence']:.2f}")
                        st.progress(detail["confidence"])

                if detail.get("explanation"):
                    st.markdown("**💡 Explanation:**")
                    st.info(detail["explanation"])
    else:
        st.info("📭 No results to display. Run reconciliation first.")


# ══════════════════════════════════════════════════════════════════════
# PAGE 4: Audit Log
# ══════════════════════════════════════════════════════════════════════

elif page == "📋 Audit Log":
    st.header("📋 Audit Log")
    st.markdown("Complete audit trail of all reconciliation actions.")

    # Search
    search = st.text_input("🔎 Search by Record ID", placeholder="e.g., pay_AbCdEf123456")

    logs = api_call("audit-log", params={"limit": 500})

    if logs:
        df = pd.DataFrame(logs)

        # Filter by search
        if search:
            df = df[df["record_id"].str.contains(search, case=False, na=False)]

        display_cols = ["created_at", "action", "record_type", "record_id", "old_state", "new_state", "reason"]
        available_cols = [c for c in display_cols if c in df.columns]

        st.markdown(f"**{len(df)} audit entries**")
        st.dataframe(df[available_cols], use_container_width=True, height=500)

        # Export button
        st.markdown("---")
        if st.button("📥 Export Reconciliation Report (CSV)", type="primary"):
            try:
                resp = requests.get(f"{API_BASE}/export", timeout=10)
                st.download_button(
                    label="⬇️ Download CSV Report",
                    data=resp.content,
                    file_name="reconciliation_report.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error(f"Export error: {e}")
    else:
        st.info("📭 No audit log entries yet. Run reconciliation first.")
