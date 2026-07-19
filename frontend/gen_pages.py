import os

pages = ['TrafficMap', 'Prediction', 'Federated', 'Training', 'Analysis', 'Results', 'About']

for p in pages:
    content = f"""import React from 'react';

const {p}: React.FC = () => {{
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">{p}</h1>
      <p className="text-textSecondary">Placeholder for {p}.</p>
    </div>
  );
}};

export default {p};
"""
    with open(f"src/pages/{p}/index.tsx", "w") as f:
        f.write(content)
