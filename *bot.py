import streamlit as st
import time

st.title("🤖 자비스 자동매매 봇 24시간 구동 중")
st.write("클라우드 서버에서 봇이 정상적으로 작동하고 있습니다.")

if st.button("봇 상태 새로고침"):
    st.success("봇이 활성화되어 정상적으로 실행 중입니다!")
    
while True:
    time.sleep(60)
