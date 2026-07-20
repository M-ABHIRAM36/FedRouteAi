from pydantic import BaseModel, Field

class PredictionRequest(BaseModel):
    road_id: str = Field(..., description="ID of the road segment", examples=["02120037"])
    speed: float = Field(..., description="Current speed in km/h", examples=[20.5])
    density: float = Field(..., description="Current density (vehicles per km)", examples=[40.0])
    travel_time: float = Field(..., description="Current travel time in minutes", examples=[12.0])
    heading: float = Field(..., description="Heading in degrees", examples=[90.0])

class PredictionResponse(BaseModel):
    prediction: str = Field(..., description="Predicted road status (e.g., Normal, Accident, Construction)", examples=["Accident"])
    confidence: float = Field(..., description="Confidence score of the prediction (0.0 to 1.0)", examples=[0.92])
    probabilities: dict[str, float] = Field(..., description="Probabilities for each class", examples=[{"Normal": 0.05, "Accident": 0.92, "Construction": 0.03}])
    inference_time_ms: int = Field(..., description="Time taken for inference in milliseconds", examples=[15])
