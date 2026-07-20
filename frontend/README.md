# FedRouteAI Frontend Dashboard

This is the official frontend interface for the **FedRouteAI** research project—a Federated Learning based Traffic Analysis and Road Event Detection platform.

## Features

- **Performance**: Built with React 18 and Vite for fast execution and Hot Module Replacement (HMR). Uses `React.lazy` and `Suspense` for aggressive code-splitting.
- **Accessibility (a11y)**: Semantic HTML and proper ARIA labels are used across the dashboard.
- **Design System**: Dark-mode primary, minimal, research-oriented UI (TensorBoard/Grafana style) using Tailwind CSS v4.
- **Visualizations**: Synthetic road network mapped onto `react-leaflet` with `CRS.Simple`, and telemetry visualized using `recharts`.
- **API Resilience**: Auto-fallback Demo Mode for predictions when the backend ML server is offline.

## Project Architecture (Milestones 1-7)

- `Dashboard`: Pipeline telemetry and aggregated statistics.
- `TrafficMap`: Synthetic road segment status visualization.
- `Prediction`: Real-time / demo-mode global model inference UI.
- `Federated`: AdaptiveFedAvg client weight dynamics.
- `Training`: Global loss, accuracy, and macro F1 curves.
- `Analysis`: Auto-generated markdown reports from the ML experiments.
- `Results`: Experiment artifact explorer.

## Local Development

1. Ensure you have Node 18+ installed.
2. Install dependencies:
   \`\`\`bash
   npm install
   \`\`\`
3. Run the development server:
   \`\`\`bash
   npm run dev
   \`\`\`
4. Open [http://localhost:5173](http://localhost:5173).

## Production Deployment (Vercel / Render)

This project includes a `vercel.json` file designed to handle React Router's client-side routing.

1. Push your code to GitHub.
2. Import the `frontend` directory into your Vercel dashboard.
3. Vercel will automatically detect Vite and run `npm run build`.
4. Deploy. The `vercel.json` ensures all sub-routes correctly redirect to `index.html`.
