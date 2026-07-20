import React, { useState } from 'react';
import { Target, Activity, Navigation, Clock, Hash } from 'lucide-react';
import { clsx } from 'clsx';

export interface PredictionFormData {
  road_id: string;
  speed: number | string;
  density: number | string;
  travel_time: number | string;
  heading: number | string;
}

interface PredictionFormProps {
  onSubmit: (data: PredictionFormData) => void;
  isLoading: boolean;
}

interface InputWrapperProps {
  label: string;
  icon: React.ElementType;
  name: string;
  type?: string;
  value: string | number;
  min?: number;
  max?: number;
  step?: number;
  isLoading: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const InputWrapper: React.FC<InputWrapperProps> = ({ 
  label, icon: Icon, name, type = 'number', value, min, max, step, isLoading, onChange 
}) => (
  <div className="flex flex-col gap-1.5">
    <label className="text-sm font-medium text-textSecondary flex items-center gap-2">
      <Icon className="w-4 h-4" /> {label}
    </label>
    <input
      type={type}
      name={name}
      value={value}
      onChange={onChange}
      min={min}
      max={max}
      step={step}
      disabled={isLoading}
      required
      className="bg-background border border-border rounded-md px-3 py-2 text-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors disabled:opacity-50"
    />
  </div>
);

export const PredictionForm: React.FC<PredictionFormProps> = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState<PredictionFormData>({
    road_id: 'HYD_SEG_0001',
    speed: 45,
    density: 30,
    travel_time: 12,
    heading: 90,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'road_id' ? value : (value === '' ? '' : Number(value))
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };



  return (
    <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-lg p-6">
      <h3 className="text-sm font-medium text-textPrimary mb-6 flex items-center gap-2">
        <Target className="w-4 h-4 text-primary" />
        Input Features
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <InputWrapper label="Road ID" icon={Hash} name="road_id" type="text" value={formData.road_id} isLoading={isLoading} onChange={handleChange} />
        <InputWrapper label="Speed (km/h)" icon={Activity} name="speed" value={formData.speed} min={0} max={120} isLoading={isLoading} onChange={handleChange} />
        <InputWrapper label="Density (veh/km)" icon={Activity} name="density" value={formData.density} min={0} max={200} isLoading={isLoading} onChange={handleChange} />
        <InputWrapper label="Travel Time (min)" icon={Clock} name="travel_time" value={formData.travel_time} min={0} max={100} isLoading={isLoading} onChange={handleChange} />
        <InputWrapper label="Heading (°)" icon={Navigation} name="heading" value={formData.heading} min={0} max={360} isLoading={isLoading} onChange={handleChange} />
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isLoading}
          className={clsx(
            'flex items-center gap-2 px-6 py-2.5 rounded-md font-medium text-sm transition-colors',
            isLoading 
              ? 'bg-primary/50 text-white/70 cursor-not-allowed'
              : 'bg-primary hover:bg-primaryHover text-white'
          )}
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              Running Inference...
            </>
          ) : (
            <>
              <Target className="w-4 h-4" />
              Predict Road Event
            </>
          )}
        </button>
      </div>
    </form>
  );
};
