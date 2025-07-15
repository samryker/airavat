FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with legacy peer deps to resolve conflicts
RUN npm install --legacy-peer-deps

# Copy the rest of the application
COPY . .

# Set NODE_ENV to production for build
ENV NODE_ENV=production

# Build the application with Vite
RUN npm run build

# Install serve to run the application
RUN npm install -g serve

# Expose the port
EXPOSE 3000

# Start the application (serve the dist folder)
CMD ["serve", "-s", "dist", "-l", "3000"] 