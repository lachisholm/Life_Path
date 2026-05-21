---

# Life Path — SvelteKit + Node.js Full Stack Project

## Features
- SvelteKit frontend (in `/frontend`)
- Node.js (Express) backend (in `/backend`)
- Docker support and npm scripts
- Modular, scalable folder structure
- Layered, alphabetized CSS/SCSS
- .env environment variable support
- Authentication-ready architecture
- Responsive, mobile-first design
- Reusable components
- Hot reload for development
- Ready for future database integration (MySQL/MongoDB)
- Email via nodemailer/SMTP
- No Flask

## Setup Instructions

### Prerequisites
- Node.js (v18+ recommended)
- npm
- Docker (optional, for containerized dev/prod)

### 1. Frontend (SvelteKit)
```
cd frontend
npm install
npm run dev
```
Visit: http://localhost:5173

### 2. Backend (Express)
```
cd backend
npm install
npm run dev
```
API: http://localhost:3001

### 3. Environment Variables
- Copy `.env.example` to `.env` in both frontend and backend folders and fill in values as needed.

### 4. Docker (optional)
```
docker-compose up --build
```

## Free Hosting Suggestions
- SvelteKit: [Vercel](https://vercel.com/) (free tier)
- Backend: [Render](https://render.com/) or [Railway](https://railway.app/) (free tier)

---

See each folder for more details and configuration.
