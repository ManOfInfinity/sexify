import os
from dataclasses import dataclass
from typing import Optional, Dict
import mutagen
from mutagen.flac import FLAC

@dataclass
class AnalysisResult:
    file_path: str
    file_size: int
    sample_rate: int
    channels: int
    bits_per_sample: int
    total_samples: int
    duration: float
    bit_depth: str
    # Note: Detailed dynamic range/spectral analysis requires numpy/scipy and is complex to port 1:1 without heavy dependencies.
    # Focusing on metadata-based analysis for now as per plan.

def analyze_track(file_path: str) -> Optional[AnalysisResult]:
    """
    Analyze a FLAC file and return its properties.
    """
    if not os.path.exists(file_path):
        return None
        
    try:
        audio = FLAC(file_path)
        info = audio.info
        
        file_size = os.path.getsize(file_path)
        
        return AnalysisResult(
            file_path=file_path,
            file_size=file_size,
            sample_rate=info.sample_rate,
            channels=info.channels,
            bits_per_sample=info.bits_per_sample,
            total_samples=int(info.length * info.sample_rate), # Approximation if total_samples not directly available
            duration=info.length,
            bit_depth=f"{info.bits_per_sample}-bit"
        )
    except Exception as e:
        print(f"Error analyzing track {file_path}: {e}")
        return None
