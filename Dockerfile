FROM python:3.10

# version
ARG APP_VERSION=$APP_VERSION
ENV APP_VERSION=$APP_VERSION
RUN echo $APP_VERSION "version is used"

# working directory
WORKDIR /backend

# System dependencies required by Playwright
# RUN apt-get update && \
#     apt-get install -y wget curl unzip fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
#     libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
#     libxdamage1 libxrandr2 xdg-utils libu2f-udev libvulkan1 libxss1 libgbm1 && \
#     rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY backend ./backend

RUN pip install --default-timeout=100 --no-cache-dir -r requirements.txt

# install Playwright and its dependencies
RUN python -m playwright install --with-deps

EXPOSE 5000

CMD ["python", "backend/app.py"]
