"""
Heat Map Visualization Service

Creates visual heat maps to highlight disease areas and skin problems on user images.
Each disease gets its own separate heat map image for clear visualization.
"""
import asyncio
import logging
import io
import base64
import random
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

logger = logging.getLogger(__name__)

class HeatMapVisualizationService:
    """
    Service for creating heat map visualizations of skin diseases and problems.
    Generates separate heat map images for each detected condition.
    """
    
    def __init__(self):
        """Initialize the heat map visualization service."""
        logger.info("[HEATMAP] Initializing Heat Map Visualization Service")
        
        # Define color schemes for different disease types with precise colors
        self.disease_colors = {
            'inflammatory': {'primary': '#FF4444', 'secondary': '#FF8888', 'alpha': 0.8, 'pinpoint': '#FF0000'},
            'pigmentary': {'primary': '#8B4513', 'secondary': '#D2691E', 'alpha': 0.7, 'pinpoint': '#8B0000'},
            'structural': {'primary': '#4169E1', 'secondary': '#87CEEB', 'alpha': 0.6, 'pinpoint': '#0000FF'},
            'genetic': {'primary': '#9370DB', 'secondary': '#DDA0DD', 'alpha': 0.7, 'pinpoint': '#800080'},
            'viral': {'primary': '#32CD32', 'secondary': '#90EE90', 'alpha': 0.6, 'pinpoint': '#00FF00'},
            'fungal': {'primary': '#FF8C00', 'secondary': '#FFA500', 'alpha': 0.7, 'pinpoint': '#FFA500'},
            'bacterial': {'primary': '#DC143C', 'secondary': '#FFB6C1', 'alpha': 0.8, 'pinpoint': '#FF1493'},
            'oncological': {'primary': '#8B0000', 'secondary': '#FF0000', 'alpha': 0.9, 'pinpoint': '#FF0000'},
            'precancerous': {'primary': '#B22222', 'secondary': '#FF6347', 'alpha': 0.8, 'pinpoint': '#FF4500'}
        }
        
        # Specific disease colors for precise identification
        self.specific_disease_colors = {
            'Early Skin Aging': {'pinpoint': '#FF6B6B', 'name': 'Pink'},
            'Skin Dehydration': {'pinpoint': '#87CEEB', 'name': 'Sky Blue'},
            'Rosacea': {'pinpoint': '#FF4444', 'name': 'Red'},
            'Dermatitis': {'pinpoint': '#FF8C00', 'name': 'Orange'},
            'Solar Lentigines (Age Spots)': {'pinpoint': '#8B4513', 'name': 'Brown'},
            'Photoaging': {'pinpoint': '#9370DB', 'name': 'Purple'},
            'Acne': {'pinpoint': '#FF1493', 'name': 'Hot Pink'},
            'Melasma': {'pinpoint': '#2F4F4F', 'name': 'Dark Slate Gray'},
            'Eczema': {'pinpoint': '#FF6347', 'name': 'Tomato'},
            'Psoriasis': {'pinpoint': '#DC143C', 'name': 'Crimson'}
        }
        
        # Default colors for unknown categories
        self.default_colors = {'primary': '#FF1493', 'secondary': '#FFB6C1', 'alpha': 0.6}
        
        logger.info("[HEATMAP SUCCESS] Heat Map Visualization Service initialized")
    
    async def generate_disease_heatmaps(
        self, 
        image_data: bytes, 
        detected_diseases: List[Dict[str, Any]], 
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Generate heat map visualizations for all detected diseases.
        
        Args:
            image_data: Original image bytes
            detected_diseases: List of detected diseases with confidence and severity
            session_id: Analysis session ID
            user_id: User ID
            
        Returns:
            Dictionary containing heat map URLs and metadata
        """
        try:
            logger.info(f"[HEATMAP] Generating heat maps for {len(detected_diseases)} diseases")
            
            # Convert image data to numpy array
            image = Image.open(io.BytesIO(image_data))
            image_np = np.array(image)
            
            heatmap_results = {
                'success': True,
                'session_id': session_id,
                'user_id': user_id,
                'total_diseases': len(detected_diseases),
                'heatmaps': [],
                'combined_heatmap_url': None
            }
            
            # Generate individual heat maps for each disease
            individual_heatmaps = []
            
            for i, disease in enumerate(detected_diseases):
                try:
                    heatmap_data = await self._create_disease_heatmap(
                        image_np, disease, i, session_id, user_id
                    )
                    individual_heatmaps.append(heatmap_data)
                    heatmap_results['heatmaps'].append(heatmap_data)
                    
                except Exception as e:
                    logger.error(f"[HEATMAP ERROR] Failed to create heatmap for {disease.get('name', 'Unknown')}: {e}")
                    continue
            
            # Generate combined heat map showing all diseases
            if individual_heatmaps:
                try:
                    combined_heatmap = await self._create_combined_heatmap(
                        image_np, detected_diseases, session_id, user_id
                    )
                    heatmap_results['combined_heatmap_url'] = combined_heatmap['url']
                    heatmap_results['combined_heatmap_data'] = combined_heatmap
                except Exception as e:
                    logger.error(f"[HEATMAP ERROR] Failed to create combined heatmap: {e}")
            
            logger.info(f"[HEATMAP SUCCESS] Generated {len(individual_heatmaps)} individual heatmaps")
            return heatmap_results
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate heatmaps: {e}")
            return {
                'success': False,
                'error': str(e),
                'heatmaps': [],
                'combined_heatmap_url': None
            }

    async def generate_heatmaps_for_specific_angle(
        self, 
        session_id: str,
        user_id: str,
        detected_diseases: List[Dict[str, Any]],
        target_angle: str
    ) -> Dict[str, Any]:
        """
        Generate heatmaps for a specific image angle only.
        This is used for parallel processing to avoid processing all images.
        """
        try:
            logger.info(f"[HEATMAP] Generating heatmaps for {target_angle} angle only")
            
            from app.services.mysql_client_service import mysql_service
            if not mysql_service.is_available():
                raise Exception("Database connection not available")
            images_result = mysql_service.fetch_all(
                "SELECT * FROM healoncal_captured_images WHERE session_id = %s AND angle = %s ORDER BY id DESC",
                (session_id, target_angle),
            )
            # Only process the latest image per angle to avoid duplicate work (e.g. 2 front images = 1 heatmap set)
            if images_result:
                images_result = images_result[:1]
            if not images_result:
                logger.warning(f"[HEATMAP] No {target_angle} images found for this session")
                return {
                    'success': True,
                    'heatmaps': [],
                    'combined_heatmap_url': None,
                    'total_diseases': len(detected_diseases),
                    'images_processed': []
                }
            
            heatmap_results = {
                'success': True,
                'heatmaps': [],
                'combined_heatmap_url': None,
                'total_diseases': len(detected_diseases),
                'images_processed': []
            }
            
            for image_record in images_result:
                try:
                    image_url = image_record['image_url']
                    angle = image_record['angle']
                    
                    # Download the original captured image (run in thread to avoid blocking event loop; allows parallel heatmap generation across angles)
                    image_data = await asyncio.to_thread(self._download_image, image_url)
                    image_np = np.array(Image.open(io.BytesIO(image_data)))
                    
                    logger.info(f"[HEATMAP] Processing {angle} image for heatmaps")
                    
                    # Generate all disease heatmaps AND the combined heatmap concurrently.
                    async def one_disease(i_disease):
                        i, disease = i_disease
                        try:
                            return await self._create_disease_heatmap_on_image(
                                image_np, disease, i, session_id, user_id, angle
                            )
                        except Exception as e:
                            logger.error(f"[HEATMAP ERROR] Failed to create heatmap for {disease.get('name', 'Unknown')} on {angle} image: {e}")
                            return None

                    async def combined_task():
                        try:
                            return await self._create_combined_heatmap_on_image(
                                image_np, detected_diseases, session_id, user_id, angle
                            )
                        except Exception as e:
                            logger.error(f"[HEATMAP ERROR] Failed to create combined heatmap for {angle} image: {e}")
                            return None

                    disease_tasks = [one_disease((i, d)) for i, d in enumerate(detected_diseases)]
                    all_results = await asyncio.gather(
                        *disease_tasks, combined_task(), return_exceptions=True
                    )
                    disease_results, combined_result = all_results[:-1], all_results[-1]
                    image_heatmaps = [r for r in disease_results if r is not None and not isinstance(r, Exception)]
                    if image_heatmaps and combined_result is not None and not isinstance(combined_result, Exception):
                        image_heatmaps.append(combined_result)
                    
                    heatmap_results['heatmaps'].extend(image_heatmaps)
                    heatmap_results['images_processed'].append({
                        'angle': angle,
                        'image_url': image_url,
                        'heatmaps_count': len(image_heatmaps)
                    })
                    
                except Exception as e:
                    logger.error(f"[HEATMAP ERROR] Failed to process {angle} image: {e}")
                    continue
            
            logger.info(f"[HEATMAP SUCCESS] Generated heatmaps for {target_angle} angle")
            return heatmap_results
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate heatmaps for {target_angle} angle: {e}")
            return {
                'success': False,
                'error': str(e),
                'heatmaps': [],
                'combined_heatmap_url': None
            }

    async def generate_heatmaps_on_captured_images(
        self, 
        session_id: str,
        user_id: str,
        detected_diseases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate heatmaps on the actual captured images from the database.
        This ensures accuracy by using the original images that were analyzed.
        
        Args:
            session_id: Session ID
            user_id: User ID
            detected_diseases: List of detected diseases
            
        Returns:
            Dictionary containing heatmap URLs and metadata
        """
        try:
            logger.info(f"[HEATMAP] Generating heatmaps on captured images for session {session_id}")
            
            from app.services.mysql_client_service import mysql_service
            if not mysql_service.is_available():
                raise Exception("Database connection not available")
            images_result = mysql_service.fetch_all(
                "SELECT * FROM healoncal_captured_images WHERE session_id = %s",
                (session_id,),
            )
            if not images_result:
                raise Exception("No captured images found for this session")
            
            heatmap_results = {
                'success': True,
                'heatmaps': [],
                'combined_heatmap_url': None,
                'total_diseases': len(detected_diseases),
                'images_processed': []
            }
            
            for image_record in images_result:
                try:
                    image_url = image_record['image_url']
                    angle = image_record['angle']
                    
                    # Download the original captured image (run in thread to avoid blocking event loop; allows parallel heatmap generation across angles)
                    image_data = await asyncio.to_thread(self._download_image, image_url)
                    image_np = np.array(Image.open(io.BytesIO(image_data)))
                    
                    logger.info(f"[HEATMAP] Processing {angle} image for heatmaps")
                    
                    # Generate heatmaps for this specific image in parallel across diseases
                    async def one_disease(i_disease):
                        i, disease = i_disease
                        try:
                            return await self._create_disease_heatmap_on_image(
                                image_np, disease, i, session_id, user_id, angle
                            )
                        except Exception as e:
                            logger.error(
                                f"[HEATMAP ERROR] Failed to create heatmap for {disease.get('name', 'Unknown')} on {angle} image: {e}"
                            )
                            return None
                    
                    tasks = [one_disease((i, d)) for i, d in enumerate(detected_diseases)]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    image_heatmaps = [r for r in results if r is not None and not isinstance(r, Exception)]
                    
                    # Generate combined heatmap for this image
                    if image_heatmaps:
                        try:
                            combined_heatmap = await self._create_combined_heatmap_on_image(
                                image_np, detected_diseases, session_id, user_id, angle
                            )
                            image_heatmaps.append(combined_heatmap)
                        except Exception as e:
                            logger.error(f"[HEATMAP ERROR] Failed to create combined heatmap for {angle} image: {e}")
                    
                    heatmap_results['heatmaps'].extend(image_heatmaps)
                    heatmap_results['images_processed'].append({
                        'angle': angle,
                        'image_url': image_url,
                        'heatmaps_count': len(image_heatmaps)
                    })
                    
                except Exception as e:
                    logger.error(f"[HEATMAP ERROR] Failed to process {angle} image: {e}")
                    continue
            
            logger.info(f"[HEATMAP SUCCESS] Generated heatmaps on {len(images_result.data)} captured images")
            return heatmap_results
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate heatmaps on captured images: {e}")
            return {
                'success': False,
                'error': str(e),
                'heatmaps': [],
                'combined_heatmap_url': None
            }

    async def _create_disease_heatmap_on_image(
        self, 
        image_np: np.ndarray, 
        disease: Dict[str, Any], 
        disease_index: int,
        session_id: str,
        user_id: str,
        angle: str
    ) -> Dict[str, Any]:
        """
        Create a heat map for a specific disease on a captured image.
        
        Args:
            image_np: Original captured image as numpy array
            disease: Disease information
            disease_index: Index of the disease
            session_id: Session ID
            user_id: User ID
            angle: Image angle (front, left, right)
            
        Returns:
            Dictionary containing heatmap URL and metadata
        """
        try:
            disease_name = disease.get('name', f'Disease_{disease_index}')
            category = disease.get('category', 'unknown')
            confidence = disease.get('confidence', 0.5)
            severity = disease.get('severity', 'mild')
            
            # Get colors for this disease category
            colors = self.disease_colors.get(category, self.default_colors)
            
            # Create pinpoint heatmap visualization (run in thread so multiple angles can run in parallel)
            heatmap_image = await asyncio.to_thread(
                self._generate_pinpoint_heatmap_overlay,
                image_np, disease_name, category, confidence, severity, angle
            )
            
            # Save heatmap to storage with angle information
            heatmap_url = await self._save_heatmap_to_storage_with_angle(
                heatmap_image, disease_name, disease_index, session_id, user_id, angle
            )
            
            return {
                'disease_name': disease_name,
                'category': category,
                'confidence': confidence,
                'severity': severity,
                'url': heatmap_url,
                'index': disease_index,
                'colors': colors,
                'angle': angle,
                'image_type': 'captured_with_heatmap'
            }
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to create heatmap for {disease.get('name', 'Unknown')} on {angle} image: {e}")
            raise

    async def _create_combined_heatmap_on_image(
        self, 
        image_np: np.ndarray, 
        detected_diseases: List[Dict[str, Any]], 
        session_id: str,
        user_id: str,
        angle: str
    ) -> Dict[str, Any]:
        """
        Create a combined heat map showing all diseases on a captured image.
        
        Args:
            image_np: Original captured image as numpy array
            detected_diseases: List of detected diseases
            session_id: Session ID
            user_id: User ID
            angle: Image angle (front, left, right)
            
        Returns:
            Dictionary containing combined heatmap URL and metadata
        """
        try:
            # Create combined heat map visualization (run in thread so multiple angles can run in parallel)
            combined_heatmap_image = await asyncio.to_thread(
                self._generate_combined_heatmap_overlay_on_captured_image,
                image_np, detected_diseases, angle
            )
            
            # Save combined heatmap to storage with angle information
            heatmap_url = await self._save_heatmap_to_storage_with_angle(
                combined_heatmap_image, "Combined", 0, session_id, user_id, angle, is_combined=True
            )
            
            return {
                'disease_name': 'Combined Heatmap',
                'category': 'combined',
                'confidence': 1.0,
                'severity': 'combined',
                'url': heatmap_url,
                'index': 0,
                'colors': {'primary': '#FF0000', 'secondary': '#FFA500', 'alpha': 0.6},
                'angle': angle,
                'image_type': 'captured_with_combined_heatmap',
                'total_diseases': len(detected_diseases)
            }
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to create combined heatmap on {angle} image: {e}")
            raise
    
    async def _create_disease_heatmap(
        self, 
        image_np: np.ndarray, 
        disease: Dict[str, Any], 
        disease_index: int,
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create a heat map for a specific disease.
        
        Args:
            image_np: Original image as numpy array
            disease: Disease information
            disease_index: Index of the disease
            session_id: Session ID
            user_id: User ID
            
        Returns:
            Dictionary containing heatmap URL and metadata
        """
        try:
            disease_name = disease.get('name', f'Disease_{disease_index}')
            category = disease.get('category', 'unknown')
            confidence = disease.get('confidence', 0.5)
            severity = disease.get('severity', 'mild')
            
            # Get colors for this disease category
            colors = self.disease_colors.get(category, self.default_colors)
            
            # Create heat map visualization
            heatmap_image = self._generate_heatmap_overlay(
                image_np, disease_name, category, confidence, severity, colors
            )
            
            # Save heatmap to storage
            heatmap_url = await self._save_heatmap_to_storage(
                heatmap_image, disease_name, disease_index, session_id, user_id
            )
            
            return {
                'disease_name': disease_name,
                'category': category,
                'confidence': confidence,
                'severity': severity,
                'url': heatmap_url,
                'index': disease_index,
                'colors': colors
            }
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to create heatmap for {disease.get('name', 'Unknown')}: {e}")
            raise
    
    def _generate_heatmap_overlay(
        self, 
        image_np: np.ndarray, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        colors: Dict[str, str]
    ) -> Image.Image:
        """
        Generate heat map overlay on the original image.
        
        Args:
            image_np: Original image as numpy array
            disease_name: Name of the disease
            category: Disease category
            confidence: Detection confidence (0-1)
            severity: Disease severity
            
        Returns:
            PIL Image with heat map overlay
        """
        try:
            # Create a copy of the original image
            overlay_image = Image.fromarray(image_np.copy())
            draw = ImageDraw.Draw(overlay_image)
            
            # Get image dimensions
            width, height = overlay_image.size
            
            # Create heat map based on disease characteristics
            heatmap_regions = self._calculate_heatmap_regions(
                image_np, disease_name, category, confidence, severity
            )
            
            # Draw heat map regions
            for region in heatmap_regions:
                x, y, w, h, intensity = region
                
                # Create semi-transparent overlay
                overlay_color = self._get_heatmap_color(colors, intensity)
                
                # Draw rectangle with transparency
                overlay = Image.new('RGBA', (w, h), overlay_color)
                overlay_image.paste(overlay, (x, y), overlay)
            
            # Add disease information overlay
            self._add_disease_info_overlay(
                overlay_image, disease_name, category, confidence, severity, colors
            )
            
            return overlay_image
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate heatmap overlay: {e}")
            # Return original image if heatmap generation fails
            return Image.fromarray(image_np)
    
    def _calculate_heatmap_regions(
        self, 
        image_np: np.ndarray, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str
    ) -> List[Tuple[int, int, int, int, float]]:
        """
        Calculate heat map regions based on disease characteristics.
        
        Args:
            image_np: Original image as numpy array
            disease_name: Name of the disease
            category: Disease category
            confidence: Detection confidence
            severity: Disease severity
            
        Returns:
            List of regions (x, y, width, height, intensity)
        """
        height, width = image_np.shape[:2]
        regions = []
        
        # Base intensity on confidence and severity
        base_intensity = confidence
        
        # Adjust intensity based on severity
        severity_multipliers = {
            'mild': 0.3,
            'moderate': 0.6,
            'high': 0.9,
            'severe': 1.0
        }
        intensity_multiplier = severity_multipliers.get(severity, 0.5)
        final_intensity = base_intensity * intensity_multiplier
        
        # Create regions based on disease type
        if category == 'inflammatory':
            # Redness and inflammation - focus on central face
            center_x, center_y = width // 2, height // 2
            regions.append((
                center_x - width // 4, center_y - height // 4,
                width // 2, height // 2, final_intensity
            ))
            
        elif category == 'pigmentary':
            # Pigmentation - focus on cheek areas
            regions.append((
                width // 6, height // 3,
                width // 3, height // 3, final_intensity
            ))
            regions.append((
                width // 2, height // 3,
                width // 3, height // 3, final_intensity
            ))
            
        elif category == 'structural':
            # Wrinkles and texture - focus on forehead and eye areas
            regions.append((
                width // 4, height // 6,
                width // 2, height // 4, final_intensity
            ))
            regions.append((
                width // 4, height // 2,
                width // 2, height // 4, final_intensity
            ))
            
        else:
            # Default - cover central face area
            regions.append((
                width // 4, height // 4,
                width // 2, height // 2, final_intensity
            ))
        
        return regions
    
    def _get_heatmap_color(self, colors: Dict[str, str], intensity: float) -> Tuple[int, int, int, int]:
        """
        Get heat map color with appropriate alpha based on intensity.
        
        Args:
            colors: Color scheme for the disease
            intensity: Heat map intensity (0-1)
            
        Returns:
            RGBA color tuple
        """
        try:
            # Convert hex colors to RGB
            primary_rgb = self._hex_to_rgb(colors['primary'])
            alpha = int(colors['alpha'] * 255 * intensity)
            
            return (*primary_rgb, alpha)
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to get heatmap color: {e}")
            return (255, 0, 0, 128)  # Default red with alpha
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _add_disease_info_overlay(
        self, 
        image: Image.Image, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        colors: Dict[str, str]
    ) -> None:
        """
        Add disease information overlay to the image.
        
        Args:
            image: PIL Image to add overlay to
            disease_name: Name of the disease
            category: Disease category
            confidence: Detection confidence
            severity: Disease severity
            colors: Color scheme
        """
        try:
            draw = ImageDraw.Draw(image)
            
            # Try to load a font, fallback to default if not available
            try:
                font_large = ImageFont.truetype("arial.ttf", 24)
                font_medium = ImageFont.truetype("arial.ttf", 18)
                font_small = ImageFont.truetype("arial.ttf", 14)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Get image dimensions
            width, height = image.size
            
            # Create semi-transparent background for text
            overlay_bg = Image.new('RGBA', (width, 120), (0, 0, 0, 150))
            image.paste(overlay_bg, (0, height - 120), overlay_bg)
            
            # Add disease name
            draw.text(
                (10, height - 110), 
                f"Disease: {disease_name}", 
                fill=(255, 255, 255, 255), 
                font=font_large
            )
            
            # Add category and severity
            draw.text(
                (10, height - 80), 
                f"Category: {category.title()} | Severity: {severity.title()}", 
                fill=(255, 255, 255, 255), 
                font=font_medium
            )
            
            # Add confidence
            draw.text(
                (10, height - 50), 
                f"Confidence: {confidence:.1%}", 
                fill=(255, 255, 255, 255), 
                font=font_medium
            )
            
            # Add color legend
            legend_size = 20
            legend_x = width - 150
            legend_y = height - 100
            
            # Draw color square
            color_square = Image.new('RGBA', (legend_size, legend_size), colors['primary'])
            image.paste(color_square, (legend_x, legend_y), color_square)
            
            draw.text(
                (legend_x + 30, legend_y + 5), 
                "Affected Area", 
                fill=(255, 255, 255, 255), 
                font=font_small
            )
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to add disease info overlay: {e}")
    
    async def _create_combined_heatmap(
        self, 
        image_np: np.ndarray, 
        detected_diseases: List[Dict[str, Any]], 
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create a combined heat map showing all diseases.
        
        Args:
            image_np: Original image as numpy array
            detected_diseases: List of all detected diseases
            session_id: Session ID
            user_id: User ID
            
        Returns:
            Dictionary containing combined heatmap URL and metadata
        """
        try:
            # Create combined overlay
            combined_image = Image.fromarray(image_np.copy())
            draw = ImageDraw.Draw(combined_image)
            
            # Get image dimensions
            width, height = combined_image.size
            
            # Create legend for all diseases
            legend_items = []
            y_offset = 20
            
            for i, disease in enumerate(detected_diseases):
                disease_name = disease.get('name', f'Disease_{i}')
                category = disease.get('category', 'unknown')
                confidence = disease.get('confidence', 0.5)
                severity = disease.get('severity', 'mild')
                
                # Get colors for this disease
                colors = self.disease_colors.get(category, self.default_colors)
                
                # Add to legend
                legend_items.append({
                    'name': disease_name,
                    'category': category,
                    'confidence': confidence,
                    'severity': severity,
                    'colors': colors,
                    'index': i
                })
                
                # Draw disease region on image
                regions = self._calculate_heatmap_regions(
                    image_np, disease_name, category, confidence, severity
                )
                
                for region in regions:
                    x, y, w, h, intensity = region
                    overlay_color = self._get_heatmap_color(colors, intensity)
                    
                    # Draw rectangle with transparency
                    overlay = Image.new('RGBA', (w, h), overlay_color)
                    combined_image.paste(overlay, (x, y), overlay)
            
            # Add comprehensive legend
            self._add_combined_legend(combined_image, legend_items)
            
            # Save combined heatmap
            heatmap_url = await self._save_heatmap_to_storage(
                combined_image, "Combined_Heatmap", 0, session_id, user_id, is_combined=True
            )
            
            return {
                'url': heatmap_url,
                'total_diseases': len(detected_diseases),
                'legend_items': legend_items
            }
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to create combined heatmap: {e}")
            raise
    
    def _add_combined_legend(
        self, 
        image: Image.Image, 
        legend_items: List[Dict[str, Any]]
    ) -> None:
        """
        Add comprehensive legend to combined heatmap.
        
        Args:
            image: PIL Image to add legend to
            legend_items: List of legend items
        """
        try:
            draw = ImageDraw.Draw(image)
            
            # Try to load fonts
            try:
                font_large = ImageFont.truetype("arial.ttf", 20)
                font_medium = ImageFont.truetype("arial.ttf", 16)
                font_small = ImageFont.truetype("arial.ttf", 12)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            width, height = image.size
            
            # Calculate legend height needed
            legend_height = 60 + (len(legend_items) * 25)
            
            # Create semi-transparent background
            overlay_bg = Image.new('RGBA', (width, legend_height), (0, 0, 0, 180))
            image.paste(overlay_bg, (0, height - legend_height), overlay_bg)
            
            # Add title
            draw.text(
                (10, height - legend_height + 10), 
                "Detected Skin Conditions - Heat Map Legend", 
                fill=(255, 255, 255, 255), 
                font=font_large
            )
            
            # Add each disease to legend
            y_offset = height - legend_height + 40
            
            for item in legend_items:
                # Draw color square
                color_square = Image.new('RGBA', (15, 15), item['colors']['primary'])
                image.paste(color_square, (10, y_offset), color_square)
                
                # Add disease info
                disease_text = f"{item['name']} ({item['severity'].title()}) - {item['confidence']:.1%}"
                draw.text(
                    (35, y_offset - 2), 
                    disease_text, 
                    fill=(255, 255, 255, 255), 
                    font=font_medium
                )
                
                y_offset += 25
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to add combined legend: {e}")
    
    async def _save_heatmap_to_storage(
        self, 
        heatmap_image: Image.Image, 
        disease_name: str, 
        disease_index: int, 
        session_id: str,
        user_id: str,
        is_combined: bool = False
    ) -> str:
        """
        Save heatmap image to storage and return URL.
        
        Args:
            heatmap_image: PIL Image to save
            disease_name: Name of the disease
            disease_index: Index of the disease
            session_id: Session ID
            user_id: User ID
            is_combined: Whether this is a combined heatmap
            
        Returns:
            Public URL of the saved heatmap
        """
        try:
            img_buffer = io.BytesIO()
            if heatmap_image.mode not in ("RGB", "RGBA"):
                heatmap_image = heatmap_image.convert("RGBA")
            heatmap_image.save(img_buffer, format="WEBP", quality=92, method=4)
            img_bytes = img_buffer.getvalue()

            import time
            timestamp = int(time.time())

            if is_combined:
                filename = f"combined_heatmap_{timestamp}.webp"
            else:
                safe_name = disease_name.replace(' ', '_').replace('/', '_')
                filename = f"heatmap_{safe_name}_{disease_index}_{timestamp}.webp"

            file_path = f"users/{user_id}/healoncal/{session_id}/heatmaps/{filename}"

            from app.services.s3_storage_service import upload_image as s3_upload_image
            image_url = s3_upload_image(file_path, img_bytes, content_type="image/webp")
            logger.info(f"[HEATMAP STORAGE] Saved heatmap: {file_path} ({len(img_bytes)}B)")
            return image_url
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to save heatmap: {e}")
            raise

    def _generate_pinpoint_heatmap_overlay(
        self, 
        image_np: np.ndarray, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        angle: str
    ) -> Image.Image:
        """
        Generate speckle heatmap overlay on the face (many small granular dots).
        Mimics the scattered white-speckle style across affected/face regions.
        """
        try:
            overlay_image = Image.fromarray(image_np.copy())
            if overlay_image.mode != "RGBA":
                overlay_image = overlay_image.convert("RGBA")
            draw = ImageDraw.Draw(overlay_image)
            width, height = overlay_image.size
            disease_color = self.specific_disease_colors.get(disease_name, {}).get("pinpoint") or \
                            self.disease_colors.get(category, self.default_colors).get("pinpoint") or \
                            self.disease_colors.get(category, self.default_colors).get("primary", "#FF1493")
            if isinstance(disease_color, dict):
                disease_color = disease_color.get("pinpoint", "#FF1493")
            if not isinstance(disease_color, str) or not disease_color.startswith("#"):
                disease_color = "#FF1493"
            regions = self._calculate_heatmap_regions_for_angle(
                image_np, disease_name, category, confidence, severity, angle
            )
            # Distinct disease color for speckles (each condition has its own color)
            try:
                hex_color = disease_color.lstrip("#")
                if len(hex_color) >= 6:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                else:
                    r, g, b = 255, 20, 147
            except Exception:
                r, g, b = 255, 20, 147
            speckle_color = (r, g, b, 210)
            seed = hash((disease_name, angle)) % (2 ** 32)
            self._draw_speckle_overlay(
                draw, width, height, regions, speckle_color, angle,
                num_speckles=450, seed=seed
            )
            self._add_disease_info_overlay_with_angle(
                overlay_image, disease_name, category, confidence, severity,
                {"primary": disease_color, "secondary": disease_color, "alpha": 0.8}, angle
            )
            return overlay_image
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate speckle heatmap: {e}")
            return Image.fromarray(image_np)

    def _generate_heatmap_overlay_on_captured_image(
        self, 
        image_np: np.ndarray, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        colors: Dict[str, str],
        angle: str
    ) -> Image.Image:
        """
        Generate heat map overlay on the captured image with angle-specific accuracy.
        
        Args:
            image_np: Original captured image as numpy array
            disease_name: Name of the disease
            category: Disease category
            confidence: Detection confidence (0-1)
            severity: Disease severity
            colors: Color scheme for the disease
            angle: Image angle (front, left, right)
            
        Returns:
            PIL Image with heat map overlay on the captured image
        """
        try:
            # Create a copy of the original captured image
            overlay_image = Image.fromarray(image_np.copy())
            draw = ImageDraw.Draw(overlay_image)
            
            # Get image dimensions
            width, height = overlay_image.size
            
            # Create heat map based on disease characteristics and angle
            heatmap_regions = self._calculate_heatmap_regions_for_angle(
                image_np, disease_name, category, confidence, severity, angle
            )
            
            # Draw heat map regions on the captured image
            for region in heatmap_regions:
                x, y, w, h, intensity = region
                
                # Create semi-transparent overlay
                overlay_color = self._get_heatmap_color(colors, intensity)
                
                # Draw rectangle with transparency
                overlay = Image.new('RGBA', (w, h), overlay_color)
                overlay_image.paste(overlay, (x, y), overlay)
            
            # Add disease information overlay with angle information
            self._add_disease_info_overlay_with_angle(
                overlay_image, disease_name, category, confidence, severity, colors, angle
            )
            
            return overlay_image
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate heatmap overlay on captured image: {e}")
            # Return original image if heatmap generation fails
            return Image.fromarray(image_np)

    def _generate_combined_heatmap_overlay_on_captured_image(
        self, 
        image_np: np.ndarray, 
        detected_diseases: List[Dict[str, Any]], 
        angle: str
    ) -> Image.Image:
        """
        Generate combined heat map overlay on the captured image showing all diseases.
        
        Args:
            image_np: Original captured image as numpy array
            detected_diseases: List of detected diseases
            angle: Image angle (front, left, right)
            
        Returns:
            PIL Image with combined heat map overlay on the captured image
        """
        try:
            overlay_image = Image.fromarray(image_np.copy())
            if overlay_image.mode != "RGBA":
                overlay_image = overlay_image.convert("RGBA")
            draw = ImageDraw.Draw(overlay_image)
            width, height = overlay_image.size
            # Draw each disease's regions in its own color (combined = multi-color heatmap)
            per_disease_speckles = max(80, 400 // max(1, len(detected_diseases)))
            for i, disease in enumerate(detected_diseases):
                disease_name = disease.get("name", f"Disease_{i}")
                category = disease.get("category", "unknown")
                confidence = disease.get("confidence", 0.5)
                severity = disease.get("severity", "mild")
                disease_regions = self._calculate_heatmap_regions_for_angle(
                    image_np, disease_name, category, confidence, severity, angle
                )
                if not disease_regions:
                    continue
                disease_color = self.specific_disease_colors.get(disease_name, {}).get("pinpoint") or \
                                self.disease_colors.get(category, self.default_colors).get("primary", "#FF1493")
                if isinstance(disease_color, dict):
                    disease_color = disease_color.get("pinpoint", "#FF1493")
                if not isinstance(disease_color, str) or not disease_color.startswith("#"):
                    disease_color = "#FF1493"
                try:
                    hex_color = disease_color.lstrip("#")
                    if len(hex_color) >= 6:
                        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
                    else:
                        r, g, b = 255, 20, 147
                except Exception:
                    r, g, b = 255, 20, 147
                speckle_color = (r, g, b, 200)
                seed = hash(("combined", angle, i, disease_name)) % (2 ** 32)
                self._draw_speckle_overlay(
                    draw, width, height, disease_regions, speckle_color, angle,
                    num_speckles=per_disease_speckles, seed=seed
                )
            self._add_combined_disease_info_overlay_with_angle(
                overlay_image, detected_diseases, angle
            )
            return overlay_image
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to generate combined heatmap overlay on captured image: {e}")
            # Return original image if heatmap generation fails
            return Image.fromarray(image_np)

    def _calculate_heatmap_regions_for_angle(
        self, 
        image_np: np.ndarray, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        angle: str
    ) -> List[Tuple[int, int, int, int, float]]:
        """
        Calculate heat map regions based on disease characteristics and image angle.
        This provides angle-specific accuracy for heatmap placement.
        
        Args:
            image_np: Original captured image as numpy array
            disease_name: Name of the disease
            category: Disease category
            confidence: Detection confidence
            severity: Disease severity
            angle: Image angle (front, left, right)
            
        Returns:
            List of regions (x, y, width, height, intensity)
        """
        height, width = image_np.shape[:2]
        regions = []
        
        # Base intensity on confidence and severity
        base_intensity = confidence
        
        # Adjust intensity based on severity
        severity_multipliers = {
            'mild': 0.3,
            'moderate': 0.6,
            'high': 0.9,
            'severe': 1.0
        }
        intensity_multiplier = severity_multipliers.get(severity, 0.5)
        final_intensity = base_intensity * intensity_multiplier
        
        # Localized regions only – affected areas per disease/angle (small patches, not full face)
        def add_region(x, y, w, h, intensity=final_intensity):
            regions.append((x, y, max(2, w), max(2, h), intensity))

        if angle == 'front':
            if disease_name == 'Early Skin Aging':
                add_region(width // 4, height // 8, width // 2, height // 8)   # forehead strip
                add_region(width // 5, height // 3, width // 5, height // 6)  # left eye area
                add_region(3 * width // 5, height // 3, width // 5, height // 6)  # right eye area
                add_region(width // 3, 2 * height // 3, width // 3, height // 8)  # mouth/nasolabial
            elif disease_name == 'Skin Dehydration':
                add_region(width // 4, height // 3, width // 6, height // 5)   # left cheek patch
                add_region(3 * width // 5, height // 3, width // 6, height // 5) # right cheek patch
                add_region(width // 3, height // 2, width // 3, height // 8)    # T-zone
            elif disease_name == 'Eczema (Atopic Dermatitis)' or category == 'inflammatory':
                add_region(width // 4, height // 3, width // 6, height // 6)   # left cheek
                add_region(3 * width // 5, height // 3, width // 6, height // 6) # right cheek
                add_region(width // 3, height // 2, width // 3, height // 10)  # chin/folds
            elif 'Solar Lentigines' in disease_name or category == 'pigmentary':
                add_region(width // 6, height // 3, width // 5, height // 5)
                add_region(width // 2, height // 3, width // 5, height // 5)
                add_region(width // 3, height // 5, width // 4, height // 10)
            elif category == 'structural':
                add_region(width // 4, height // 6, width // 2, height // 10)
                add_region(width // 4, height // 2, width // 2, height // 8)
            else:
                add_region(width // 3, height // 3, width // 3, height // 4)
        elif angle == 'left':
            if disease_name == 'Early Skin Aging':
                add_region(width // 6, height // 5, width // 4, height // 6)
                add_region(width // 4, height // 2, width // 5, height // 6)
            elif disease_name == 'Skin Dehydration' or disease_name == 'Eczema (Atopic Dermatitis)' or category == 'inflammatory':
                add_region(width // 5, height // 3, width // 4, height // 5)
                add_region(width // 4, height // 2, width // 5, height // 5)
            elif category == 'pigmentary':
                add_region(width // 6, height // 3, width // 4, height // 5)
            elif category == 'structural':
                add_region(width // 6, height // 6, width // 3, height // 8)
                add_region(width // 5, height // 2, width // 4, height // 6)
            else:
                add_region(width // 5, height // 3, width // 3, height // 4)
        elif angle == 'right':
            if disease_name == 'Early Skin Aging':
                add_region(2 * width // 5, height // 5, width // 4, height // 6)
                add_region(2 * width // 5, height // 2, width // 5, height // 6)
            elif disease_name == 'Skin Dehydration' or disease_name == 'Eczema (Atopic Dermatitis)' or category == 'inflammatory':
                add_region(2 * width // 5, height // 3, width // 4, height // 5)
                add_region(2 * width // 5, height // 2, width // 5, height // 5)
            elif category == 'pigmentary':
                add_region(width // 2, height // 3, width // 4, height // 5)
            elif category == 'structural':
                add_region(width // 2, height // 6, width // 3, height // 8)
                add_region(2 * width // 5, height // 2, width // 4, height // 6)
            else:
                add_region(width // 3, height // 3, width // 3, height // 4)
        return regions

    def _add_disease_info_overlay_with_angle(
        self, 
        image: Image.Image, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        colors: Dict[str, str],
        angle: str
    ) -> None:
        """
        Add disease information overlay to the image with angle information.
        """
        try:
            draw = ImageDraw.Draw(image)
            width, height = image.size
            
            # Create semi-transparent background for text
            text_bg = Image.new('RGBA', (width, 200), (0, 0, 0, 100))
            image.paste(text_bg, (0, height - 200), text_bg)
            
            # Add text information
            text_y = height - 180
            draw.text((20, text_y), f"Disease: {disease_name}", fill=(255, 255, 255, 255))
            draw.text((20, text_y + 30), f"Category: {category}", fill=(255, 255, 255, 255))
            draw.text((20, text_y + 60), f"Confidence: {confidence:.2f}", fill=(255, 255, 255, 255))
            draw.text((20, text_y + 90), f"Severity: {severity}", fill=(255, 255, 255, 255))
            draw.text((20, text_y + 120), f"Angle: {angle}", fill=(255, 255, 255, 255))
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to add disease info overlay: {e}")

    def _add_combined_disease_info_overlay_with_angle(
        self, 
        image: Image.Image, 
        detected_diseases: List[Dict[str, Any]], 
        angle: str
    ) -> None:
        """
        Add combined disease information overlay to the image with angle information.
        """
        try:
            draw = ImageDraw.Draw(image)
            width, height = image.size
            
            # Create semi-transparent background for text
            text_bg = Image.new('RGBA', (width, 250), (0, 0, 0, 100))
            image.paste(text_bg, (0, height - 250), text_bg)
            
            # Add text information
            text_y = height - 230
            draw.text((20, text_y), f"Combined Analysis - {angle} view", fill=(255, 255, 255, 255))
            draw.text((20, text_y + 30), f"Total Diseases: {len(detected_diseases)}", fill=(255, 255, 255, 255))
            
            # List diseases
            for i, disease in enumerate(detected_diseases[:5]):  # Show first 5 diseases
                disease_name = disease.get('name', f'Disease_{i}')
                confidence = disease.get('confidence', 0.5)
                draw.text((20, text_y + 60 + (i * 25)), f"• {disease_name} ({confidence:.2f})", fill=(255, 255, 255, 255))
            
            if len(detected_diseases) > 5:
                draw.text((20, text_y + 60 + (5 * 25)), f"... and {len(detected_diseases) - 5} more", fill=(255, 255, 255, 255))
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to add combined disease info overlay: {e}")

    async def _save_heatmap_to_storage_with_angle(
        self, 
        heatmap_image: Image.Image, 
        disease_name: str, 
        disease_index: int, 
        session_id: str,
        user_id: str,
        angle: str,
        is_combined: bool = False
    ) -> str:
        """
        Save heatmap image to storage with angle information and return URL.
        
        Args:
            heatmap_image: PIL Image to save
            disease_name: Name of the disease
            disease_index: Index of the disease
            session_id: Session ID
            user_id: User ID
            angle: Image angle (front, left, right)
            is_combined: Whether this is a combined heatmap
            
        Returns:
            Public URL of the saved heatmap
        """
        try:
            # Encode as WebP: ~3-5x smaller than PNG at visually identical
            # quality, which cuts S3 PUT time and client-side download.
            img_buffer = io.BytesIO()
            if heatmap_image.mode not in ("RGB", "RGBA"):
                heatmap_image = heatmap_image.convert("RGBA")
            heatmap_image.save(img_buffer, format="WEBP", quality=92, method=4)
            img_bytes = img_buffer.getvalue()

            import time
            timestamp = int(time.time())

            if is_combined:
                filename = f"combined_heatmap_{angle}_{timestamp}.webp"
            else:
                safe_name = disease_name.replace(' ', '_').replace('/', '_')
                filename = f"heatmap_{safe_name}_{angle}_{disease_index}_{timestamp}.webp"

            file_path = f"users/{user_id}/healoncal/{session_id}/heatmaps/{filename}"

            from app.services.s3_storage_service import upload_image as s3_upload_image
            image_url = await asyncio.to_thread(s3_upload_image, file_path, img_bytes, "image/webp")
            logger.info(f"[HEATMAP STORAGE] Saved heatmap with angle: {file_path} ({len(img_bytes)}B)")
            return image_url
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to save heatmap with angle: {e}")
            raise

    def _calculate_pinpoint_locations(
        self, 
        image_np: np.ndarray, 
        disease_name: str, 
        category: str, 
        confidence: float, 
        severity: str,
        angle: str
    ) -> List[Tuple[int, int, int, float]]:
        """
        Calculate pinpoint locations for disease-specific areas.
        Returns list of (x, y, size, intensity) tuples.
        """
        height, width = image_np.shape[:2]
        locations = []
        
        # Base intensity on confidence
        base_intensity = confidence
        
        # Adjust intensity based on severity
        severity_multipliers = {
            'mild': 0.3,
            'moderate': 0.6,
            'severe': 1.0
        }
        intensity_multiplier = severity_multipliers.get(severity, 0.5)
        final_intensity = base_intensity * intensity_multiplier
        
        # Calculate pinpoint locations based on disease type and angle
        if disease_name == 'Early Skin Aging':
            # Focus on forehead, eye areas, and mouth lines
            if angle == 'front':
                locations.extend([
                    (width // 2, height // 6, 8, final_intensity),  # Forehead center
                    (width // 3, height // 3, 6, final_intensity),  # Left eye area
                    (2 * width // 3, height // 3, 6, final_intensity),  # Right eye area
                    (width // 2, 2 * height // 3, 5, final_intensity),  # Mouth area
                ])
            elif angle == 'left':
                locations.extend([
                    (width // 4, height // 4, 7, final_intensity),  # Left side forehead
                    (width // 3, height // 2, 6, final_intensity),  # Left side eye
                ])
            elif angle == 'right':
                locations.extend([
                    (3 * width // 4, height // 4, 7, final_intensity),  # Right side forehead
                    (2 * width // 3, height // 2, 6, final_intensity),  # Right side eye
                ])
                
        elif disease_name == 'Rosacea':
            # Focus on central face area (cheeks, nose)
            if angle == 'front':
                locations.extend([
                    (width // 3, height // 2, 10, final_intensity),  # Left cheek
                    (2 * width // 3, height // 2, 10, final_intensity),  # Right cheek
                    (width // 2, height // 2, 8, final_intensity),  # Nose area
                ])
            elif angle == 'left':
                locations.extend([
                    (width // 3, height // 2, 12, final_intensity),  # Left cheek prominence
                ])
            elif angle == 'right':
                locations.extend([
                    (2 * width // 3, height // 2, 12, final_intensity),  # Right cheek prominence
                ])
                
        elif disease_name == 'Solar Lentigines (Age Spots)':
            # Focus on sun-exposed areas
            if angle == 'front':
                locations.extend([
                    (width // 4, height // 3, 6, final_intensity),  # Left cheek
                    (3 * width // 4, height // 3, 6, final_intensity),  # Right cheek
                    (width // 2, height // 4, 5, final_intensity),  # Forehead
                ])
            elif angle == 'left':
                locations.extend([
                    (width // 3, height // 3, 8, final_intensity),  # Left side cheek
                ])
            elif angle == 'right':
                locations.extend([
                    (2 * width // 3, height // 3, 8, final_intensity),  # Right side cheek
                ])
                
        else:
            # Default pinpoint locations for other diseases
            if angle == 'front':
                locations.extend([
                    (width // 2, height // 2, 8, final_intensity),  # Center
                ])
            elif angle == 'left':
                locations.extend([
                    (width // 3, height // 2, 8, final_intensity),  # Left side
                ])
            elif angle == 'right':
                locations.extend([
                    (2 * width // 3, height // 2, 8, final_intensity),  # Right side
                ])
        
        return locations

    def _get_face_region_for_speckles(
        self, width: int, height: int, angle: str
    ) -> Tuple[int, int, int, int]:
        """
        Return (x, y, width, height) of the face region for speckle overlay.
        Uses a central area so speckles cover forehead, cheeks, nose, chin.
        """
        margin_w = max(20, width // 8)
        margin_h = max(20, height // 10)
        x = margin_w
        y = margin_h
        w = width - 2 * margin_w
        h = height - 2 * margin_h
        return (x, y, w, h)

    def _draw_speckle_overlay(
        self,
        draw: ImageDraw.Draw,
        width: int,
        height: int,
        regions: List[Tuple[int, int, int, int, float]],
        speckle_color: Tuple[int, int, int, int],
        angle: str,
        num_speckles: int = 450,
        seed: Optional[int] = None,
    ) -> None:
        """
        Draw many small speckles across the given regions — vectorised.
        Was: 450 Python-level `draw.ellipse` calls per heatmap (~9,500 PIL
        calls across 21 heatmaps). Now: numpy generates every position + radius
        in one shot, stamps are painted via slicing, single `alpha_composite`
        at the end.
        """
        if width <= 0 or height <= 0 or not regions:
            return
        image = getattr(draw, "_image", None) or getattr(draw, "im", None)
        target = draw._image if hasattr(draw, "_image") else None
        # PIL's ImageDraw stores the backing image on `._image`. If we can't
        # reach it (different PIL version / wrapped Draw), fall back to the
        # original pure-PIL path so behavior is preserved.
        if target is None:
            return self._draw_speckle_overlay_pil_fallback(
                draw, width, height, regions, speckle_color, angle, num_speckles, seed
            )

        rng = np.random.default_rng(seed if seed is not None else None)
        min_r, max_r = 1, 3
        total_area = max(1, width * height)

        # Build per-region (px, py, radius) arrays.
        xs_list: List[np.ndarray] = []
        ys_list: List[np.ndarray] = []
        rs_list: List[np.ndarray] = []
        for (rx, ry, rw, rh, intensity) in regions:
            n = max(15, int(num_speckles * (rw * rh) / total_area * (0.5 + 0.5 * intensity)))
            if n <= 0:
                continue
            xs_list.append(rx + rng.integers(0, max(1, rw), size=n))
            ys_list.append(ry + rng.integers(0, max(1, rh), size=n))
            rs_list.append(rng.integers(min_r, max_r + 1, size=n))
        if not xs_list:
            return
        xs = np.concatenate(xs_list).astype(np.int32)
        ys = np.concatenate(ys_list).astype(np.int32)
        rs = np.concatenate(rs_list).astype(np.int32)

        # Per-speckle alpha (30% of speckles get a reduced alpha, same as before).
        base_alpha = int(speckle_color[3])
        low_alpha = max(80, base_alpha - 40)
        alpha_mask_low = rng.random(xs.shape[0]) < 0.3
        alphas = np.where(alpha_mask_low, low_alpha, base_alpha).astype(np.uint8)

        # Build an RGBA overlay via numpy. For our small max radius of 3, a
        # 7x7 filled-disc stamp is exact.
        overlay_arr = np.zeros((height, width, 4), dtype=np.uint8)
        r_col, g_col, b_col = int(speckle_color[0]), int(speckle_color[1]), int(speckle_color[2])

        # Pre-compute disc stamps for each radius value.
        stamps: Dict[int, np.ndarray] = {}
        for r in range(min_r, max_r + 1):
            yy, xx = np.ogrid[-r : r + 1, -r : r + 1]
            stamps[r] = (xx * xx + yy * yy <= r * r).astype(np.bool_)

        for px, py, r, a in zip(xs, ys, rs, alphas):
            mask = stamps[int(r)]
            mh, mw = mask.shape
            x0 = int(px) - r
            y0 = int(py) - r
            x1 = x0 + mw
            y1 = y0 + mh
            # Clip to image bounds.
            sx0 = max(0, -x0)
            sy0 = max(0, -y0)
            x0c = max(0, x0)
            y0c = max(0, y0)
            x1c = min(width, x1)
            y1c = min(height, y1)
            if x1c <= x0c or y1c <= y0c:
                continue
            sub = mask[sy0 : sy0 + (y1c - y0c), sx0 : sx0 + (x1c - x0c)]
            # Max-alpha compositing where existing alpha is lower.
            region = overlay_arr[y0c:y1c, x0c:x1c]
            region[..., 0] = np.where(sub, r_col, region[..., 0])
            region[..., 1] = np.where(sub, g_col, region[..., 1])
            region[..., 2] = np.where(sub, b_col, region[..., 2])
            region[..., 3] = np.where(sub & (a > region[..., 3]), a, region[..., 3])

        overlay_img = Image.fromarray(overlay_arr, mode="RGBA")
        # Composite onto the backing image of the draw object.
        if target.mode != "RGBA":
            target_rgba = target.convert("RGBA")
            target_rgba.alpha_composite(overlay_img)
            target.paste(target_rgba)
        else:
            target.alpha_composite(overlay_img)

    def _draw_speckle_overlay_pil_fallback(
        self,
        draw: ImageDraw.Draw,
        width: int,
        height: int,
        regions: List[Tuple[int, int, int, int, float]],
        speckle_color: Tuple[int, int, int, int],
        angle: str,
        num_speckles: int,
        seed: Optional[int],
    ) -> None:
        """Original PIL-loop implementation, kept as a safety net."""
        rng = random.Random(seed) if seed is not None else random.Random()
        min_r, max_r = 1, 3
        positions: List[Tuple[int, int, int]] = []
        total_area = width * height
        for (rx, ry, rw, rh, intensity) in regions:
            n = max(15, int(num_speckles * (rw * rh) / max(1, total_area) * (0.5 + 0.5 * intensity)))
            for _ in range(n):
                px = rx + rng.randint(0, max(1, rw - 1))
                py = ry + rng.randint(0, max(1, rh - 1))
                r = rng.randint(min_r, max_r)
                positions.append((px, py, r))
        for (px, py, r) in positions:
            alpha = speckle_color[3]
            if rng.random() < 0.3:
                alpha = max(80, speckle_color[3] - 40)
            fill = (speckle_color[0], speckle_color[1], speckle_color[2], alpha)
            draw.ellipse([px - r, py - r, px + r, py + r], fill=fill, outline=fill)

    def _draw_pinpoint_marker(
        self, 
        draw: ImageDraw.Draw, 
        x: int, 
        y: int, 
        size: int, 
        intensity: float, 
        color: str, 
        disease_name: str
    ) -> None:
        """
        Draw a pinpoint marker at the specified location.
        Creates a colored dot with disease-specific styling.
        """
        try:
            # Calculate alpha based on intensity
            alpha = int(255 * intensity)
            
            # Create pinpoint marker (colored circle)
            radius = size // 2
            
            # Draw outer ring (darker)
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=color,
                outline=color,
                width=2
            )
            
            # Draw inner dot (lighter)
            inner_radius = max(1, radius // 2)
            draw.ellipse(
                [x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius],
                fill='white',
                outline=color,
                width=1
            )
            
        except Exception as e:
            logger.error(f"[HEATMAP ERROR] Failed to draw pinpoint marker: {e}")

    def _download_image(self, image_url: str) -> bytes:
        """
        Download image data for heatmap generation.
        
        Images and heatmaps are stored in S3 or as generic HTTP URLs.
        For S3 URLs we use the S3 client; any non-S3 URL is treated as a normal HTTP resource.
        """
        from app.services.s3_storage_service import download_image as storage_download
        file_data = storage_download(image_url)
        if file_data:
            return file_data

        # Any other URL – treat as public HTTP resource
        import requests
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        if not response.content:
            raise Exception("Downloaded image is empty")
        return response.content


# Global instance
heatmap_visualization_service = HeatMapVisualizationService()
