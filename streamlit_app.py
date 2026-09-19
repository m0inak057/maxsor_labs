import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Support Decision Assistant", page_icon="🎫", layout="centered")


def api_post(endpoint: str, payload: dict, token: str | None = None) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(f"{API_BASE}{endpoint}", json=payload, headers=headers)


def api_get(endpoint: str, token: str) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    return requests.get(f"{API_BASE}{endpoint}", headers=headers)


def show_login_page():
    st.title("🎫 Support Decision Assistant")
    st.markdown("---")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_btn", use_container_width=True):
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                resp = api_post("/login", {"email": email, "password": password})
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["token"] = data["access_token"]
                    st.session_state["email"] = email
                    st.session_state["page"] = "new_decision"
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Login failed."))

    with tab_register:
        st.subheader("Register")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register", key="register_btn", use_container_width=True):
            if not reg_email or not reg_password:
                st.error("Please enter both email and password.")
            elif len(reg_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                resp = api_post("/register", {"email": reg_email, "password": reg_password})
                if resp.status_code == 201:
                    st.success("Account created! Please login.")
                else:
                    st.error(resp.json().get("detail", "Registration failed."))


def show_sidebar():
    with st.sidebar:
        st.markdown(f"**Logged in as**\n\n{st.session_state.get('email', '')}")
        st.markdown("---")
        if st.button("📝 New Decision", use_container_width=True):
            st.session_state["page"] = "new_decision"
            st.rerun()
        if st.button("📋 History", use_container_width=True):
            st.session_state["page"] = "history"
            st.rerun()
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            for key in ["token", "email", "page"]:
                st.session_state.pop(key, None)
            st.rerun()


def show_decision_result(decision: dict):
    action = decision.get("action", "")
    confidence = decision.get("confidence", 0)
    reason = decision.get("reason", "")
    sources = decision.get("sources", [])

    if action == "NEEDS_MORE_INFORMATION":
        st.warning(f"**Action: {action}**")
    elif action in ("APPROVE_RETURN", "APPROVE_REFUND_OR_REPLACEMENT", "APPROVE_REPLACEMENT",
                    "CANCEL_AND_REFUND", "REPLACE_CORRECT_ITEM", "OFFER_REPLACEMENT_OR_REFUND"):
        st.success(f"**Action: {action}**")
    elif action in ("REJECT_FOOD_RETURN", "REJECT_OPENED_ITEM", "REJECT_OUTSIDE_WINDOW",
                    "CANNOT_CANCEL_AFTER_DISPATCH"):
        st.error(f"**Action: {action}**")
    else:
        st.info(f"**Action: {action}**")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Confidence", f"{int(confidence * 100)}%")
    with col2:
        st.metric("Sources", len(sources))

    st.markdown("**Reason**")
    st.markdown(reason)

    st.markdown("**Policy sources used**")
    for source in sources:
        st.markdown(f"- `{source}`")


def show_new_decision_page():
    show_sidebar()
    st.title("📝 New Decision")
    st.markdown("Enter the customer support ticket below and click Analyze.")
    st.markdown("---")

    message = st.text_area(
        "Customer ticket",
        placeholder="e.g. My order arrived damaged yesterday and I need a refund.",
        height=120,
        key="ticket_message",
    )

    if st.button("Analyze", use_container_width=True, type="primary"):
        if not message.strip():
            st.error("Please enter a ticket message.")
        else:
            with st.spinner("Analyzing ticket..."):
                resp = api_post(
                    "/tickets",
                    {"message": message},
                    token=st.session_state["token"],
                )
            if resp.status_code == 201:
                data = resp.json()
                st.markdown("---")
                st.subheader("Decision")
                show_decision_result(data["decision"])
            elif resp.status_code == 401:
                st.error("Session expired. Please login again.")
                for key in ["token", "email", "page"]:
                    st.session_state.pop(key, None)
                st.rerun()
            else:
                st.error(f"Error: {resp.json().get('detail', 'Something went wrong.')}")


def show_history_page():
    show_sidebar()
    st.title("📋 Ticket History")
    st.markdown("---")

    resp = api_get("/tickets", token=st.session_state["token"])
    if resp.status_code == 401:
        st.error("Session expired. Please login again.")
        for key in ["token", "email", "page"]:
            st.session_state.pop(key, None)
        st.rerun()
        return

    tickets = resp.json()
    if not tickets:
        st.info("No tickets yet. Submit one from the New Decision page.")
        return

    for ticket in tickets:
        decision = ticket.get("decision", {})
        action = decision.get("action", "PENDING") if decision else "PENDING"
        created = ticket["created_at"][:19].replace("T", " ")
        preview = ticket["message"][:60] + ("..." if len(ticket["message"]) > 60 else "")

        with st.expander(f"[{created}]  {action}  —  {preview}"):
            st.markdown(f"**Full message:** {ticket['message']}")
            st.markdown("---")
            if decision:
                show_decision_result(decision)
            else:
                st.warning("No decision recorded for this ticket.")


def main():
    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    token = st.session_state.get("token")

    if not token:
        show_login_page()
        return

    page = st.session_state.get("page", "new_decision")
    if page == "new_decision":
        show_new_decision_page()
    elif page == "history":
        show_history_page()
    else:
        show_new_decision_page()


if __name__ == "__main__":
    main()
