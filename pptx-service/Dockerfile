FROM node:20-slim

# Install LibreOffice (for PPTX→PDF) and poppler-utils (for PDF→images)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    poppler-utils \
    fonts-liberation \
    fonts-dejavu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Node dependencies first (layer cache)
COPY package.json ./
RUN npm install --omit=dev

# Install custom fonts from canvas-design skill
COPY fonts/ /usr/share/fonts/custom/
RUN fc-cache -f -v

COPY . .

EXPOSE 3001

CMD ["node", "server.js"]
