import streamlit as st
from analyzer import run_full_analysis, stream_coach_response

st.set_page_config(page_title="Chess AI Coach", page_icon="♟️", layout="wide")

st.title("♟️ AI Chess Coach")

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if "initial_analysis" not in st.session_state:
    st.session_state.initial_analysis = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

username = st.sidebar.text_input("Chess.com username")
analyze_clicked = st.sidebar.button("Analyze Last Game")

if analyze_clicked:
    if not username.strip():
        st.sidebar.error("Please enter a username.")
    else:
        with st.spinner("Fetching game and analyzing with Stockfish..."):
            result = run_full_analysis(username.strip())

        if result is None:
            st.error("Could not analyze the game. Check username, Stockfish, or network.")
            st.session_state.analysis = None
            st.session_state.initial_analysis = None
            st.session_state.chat_history = []
        else:
            st.session_state.analysis = result
            st.session_state.initial_analysis = None
            st.session_state.chat_history = []

if st.session_state.analysis:
    ctx = st.session_state.analysis["game_ctx"]

    st.subheader("Game Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("You", f"{ctx['player']} ({ctx['player_color']})")
    col2.metric("Opponent", ctx["opponent"])
    col3.metric("Result", ctx["result"])
    col4.metric("Outcome", ctx["player_outcome"])

    st.caption(f"{ctx['event']} · {ctx['date']}")

    st.divider()
    st.subheader("AI Coach Analysis")

    if st.session_state.initial_analysis is None:
        with st.spinner("Coach is reviewing your game..."):
            analysis_text = st.write_stream(
                stream_coach_response(st.session_state.analysis["messages"])
            )
        st.session_state.initial_analysis = analysis_text
        st.session_state.analysis["messages"].append(
            {"role": "assistant", "content": analysis_text}
        )
    else:
        st.markdown(st.session_state.initial_analysis)

    if st.session_state.initial_analysis:
        st.divider()
        st.subheader("Discuss with Coach")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask about your game..."):
            st.session_state.analysis["messages"].append(
                {"role": "user", "content": prompt}
            )
            st.session_state.chat_history.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                response = st.write_stream(
                    stream_coach_response(st.session_state.analysis["messages"])
                )

            st.session_state.analysis["messages"].append(
                {"role": "assistant", "content": response}
            )
            st.session_state.chat_history.append(
                {"role": "assistant", "content": response}
            )
else:
    st.info("Enter your Chess.com username in the sidebar and click **Analyze Last Game**.")

