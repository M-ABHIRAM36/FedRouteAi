import React from 'react';
import { Link } from 'react-router-dom';
import { Map, ArrowLeft } from 'lucide-react';

const NotFound: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] text-center px-4">
      <div className="relative mb-8">
        <Map className="w-24 h-24 text-primary opacity-20" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-4xl font-bold text-white tracking-widest">404</span>
        </div>
      </div>
      
      <h2 className="text-xl font-semibold text-white mb-2">Off the beaten path</h2>
      <p className="text-sm text-textSecondary max-w-md mb-8">
        The route you are looking for doesn't exist in our federated network. It might have been moved or deleted.
      </p>
      
      <Link 
        to="/" 
        className="flex items-center gap-2 px-6 py-2.5 bg-primary hover:bg-primaryHover text-white rounded-md text-sm font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Return to Dashboard
      </Link>
    </div>
  );
};

export default NotFound;
