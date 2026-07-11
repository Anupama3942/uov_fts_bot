FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make the start script executable
RUN chmod +x start.sh

# Expose the Streamlit port
EXPOSE 8501

# Run the start script to launch both apps
CMD ["./start.sh"]