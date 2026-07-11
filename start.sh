#!/bin/bash

# Start the Telegram Bot in the background
python bot.py &

# Start the Streamlit Admin Panel on port 8501
streamlit run admin_panel.py --server.port=8501 --server.address=0.0.0.0