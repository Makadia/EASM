import streamlit as st
import requests
import urllib.parse
from datetime import datetime
import time
import pandas as pd
import json

# Define color mappings for statuses
STATUS_COLORS = {
    "scheduled": "#BFDBFE",
    "queued": "#FEF08A", 
    "inprogress": "#FED7AA",
    "completed": "#BBF7D0",
    "failed": "#FECACA",
    "queued(retry)": "#FDE68A",
    "inprogress(retry)": "#FDBA74",
    "authenticationfailed": "#FCA5A5",
    "statusretrievalfailed": "#FECACA"
}

def get_auth_token(username, password, gateway_url):
    """Authenticate with API and return the auth token."""
    auth_url = f"https://{gateway_url}/auth"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "username": username,
        "password": password,
        "token": "true",
        "permissions": "true"
    }
    try:
        response = requests.post(auth_url, headers=headers, data=data)
        if response.status_code == 201:
            token = response.text.strip()
            if token:
                return token, None
            return None, "Empty token received"
        return None, f"HTTP {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return None, str(e)

def get_profile_status(auth_token, gateway_url):
    """Retrieve profile status using the auth token."""
    status_url = f"https://{gateway_url}/easm/v2/profile/status"
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {auth_token}"
    }
    try:
        response = requests.get(status_url, headers=headers)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)

def delete_profile(auth_token, gateway_url, profile_name):
    """Delete a profile using the auth token."""
    delete_url = f"https://{gateway_url}/easm/v2/profile?profileName={urllib.parse.quote(profile_name)}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    try:
        response = requests.delete(delete_url, headers=headers)
        response.raise_for_status()
        return True, None
    except requests.exceptions.RequestException as e:
        return False, str(e)

def generate_usernames(base_username, start, end):
    """Generate username variations based on the range."""
    usernames = []
    for i in range(start, end + 1):
        if i == 0:
            usernames.append(base_username)
        else:
            usernames.append(f"{base_username}{i}")
    return usernames

def main():
    st.set_page_config(
        page_title="EASM Profile Manager",
        page_icon="🔐",
        layout="wide"
    )

    # Application title
    st.title("EASM Profile Manager")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        gateway_url = st.text_input(
            "API Gateway URL",
            placeholder="e.g., gateway.qg1.apps.qualysksa.com",
            key="gateway_url"
        )
        
        base_username = st.text_input(
            "Base Username",
            placeholder="e.g., easmrAkm",
            key="base_username"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            start_num = st.number_input("Start Number", min_value=0, value=0)
        with col2:
            end_num = st.number_input("End Number", min_value=0, value=3)
            
        password = st.text_input("Password", type="password")
        
        if st.button("Connect", type="primary", use_container_width=True):
            if not all([gateway_url, base_username, password]):
                st.error("Please fill in all required fields.")
                st.stop()
                
            if end_num < start_num:
                st.error("End number must be greater than or equal to start number.")
                st.stop()
                
            # Generate usernames and authenticate
            usernames = generate_usernames(base_username, start_num, end_num)
            tokens = {}
            
            with st.spinner("Authenticating..."):
                for username in usernames:
                    token, error = get_auth_token(username, password, gateway_url)
                    if token:
                        tokens[username] = token
                        st.success(f"✅ {username}: Authenticated")
                    else:
                        st.error(f"❌ {username}: {error}")
                
                st.session_state.tokens = tokens
                st.rerun()

    # Main content
    if 'tokens' in st.session_state and st.session_state.tokens:
        # Initialize or update profiles data
        if 'update_counter' not in st.session_state:
            st.session_state.update_counter = 0
            
        # Fetch profiles data
        all_profiles = []
        for username, token in st.session_state.tokens.items():
            profiles, error = get_profile_status(token, gateway_url)
            if profiles:
                for profile in profiles:
                    all_profiles.append({
                        "username": username,
                        "profileName": profile.get("profileName", "N/A"),
                        "status": profile.get("status", "Unknown"),
                        "lastConfiguredOn": profile.get("lastConfiguredOn", "N/A"),
                        "nextScheduledSyncOn": profile.get("nextScheduledSyncOn", "N/A"),
                        "lastDiscoveryCompletedOn": profile.get("lastDiscoveryCompletedOn", "N/A")
                    })
            else:
                all_profiles.append({
                    "username": username,
                    "profileName": "N/A",
                    "status": "Status Retrieval Failed",
                    "lastConfiguredOn": "N/A",
                    "nextScheduledSyncOn": "N/A",
                    "lastDiscoveryCompletedOn": "N/A"
                })

        # Convert to DataFrame for better handling
        df = pd.DataFrame(all_profiles)
        
        # Search filter
        search = st.text_input("🔍 Search profiles", placeholder="Filter by username, profile name, or status...")
        if search:
            mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
            df = df[mask]
            
        # Display profiles table with checkboxes
        if not df.empty:
            selected_profiles = []
            
            # Create select all checkbox
            select_all = st.checkbox("Select All")
            
            # Create a container for the table
            table_container = st.container()
            
            with table_container:
                for idx, row in df.iterrows():
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([0.5, 2, 2, 1.5, 2, 2, 2])
                    
                    with col1:
                        selected = st.checkbox("", key=f"select_{idx}", value=select_all)
                        if selected:
                            selected_profiles.append({"username": row["username"], "profileName": row["profileName"]})
                            
                    with col2:
                        st.write(row["username"])
                    with col3:
                        st.write(row["profileName"])
                    with col4:
                        status_color = STATUS_COLORS.get(row["status"].lower().replace(" ", ""), "#6B7280")
                        st.markdown(
                            f'<div style="background-color: {status_color}; padding: 5px 10px; '
                            f'border-radius: 12px; color: black; font-size: 0.9em; display: inline-block;">'
                            f'{row["status"]}</div>',
                            unsafe_allow_html=True
                        )
                    with col5:
                        st.write(row["lastConfiguredOn"])
                    with col6:
                        st.write(row["nextScheduledSyncOn"])
                    with col7:
                        st.write(row["lastDiscoveryCompletedOn"])
                        
            # Bulk delete button
            if selected_profiles:
                if st.button(f"Delete Selected ({len(selected_profiles)} profiles)", type="primary"):
                    delete_success = []
                    delete_failed = []
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, profile in enumerate(selected_profiles):
                        status_text.write(f"Deleting {profile['profileName']}...")
                        success, error = delete_profile(
                            st.session_state.tokens[profile["username"]],
                            gateway_url,
                            profile["profileName"]
                        )
                        
                        if success:
                            delete_success.append(profile["profileName"])
                        else:
                            delete_failed.append((profile["profileName"], error))
                            
                        progress_bar.progress((i + 1) / len(selected_profiles))
                        
                    if delete_success:
                        st.success(f"Successfully deleted {len(delete_success)} profiles")
                    if delete_failed:
                        for profile, error in delete_failed:
                            st.error(f"Failed to delete {profile}: {error}")
                            
                    time.sleep(2)
                    st.rerun()
            
        # Auto-refresh
        time.sleep(30)
        st.session_state.update_counter += 1
        st.rerun()

if __name__ == "__main__":
    main()
