# SourceIO Integration for BlenderVertexLitGeneric
# This module adds a "Import MDL (Softlamps)" operator that uses our material pipeline

import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty

# Compatibility wrapper for SourceIO logger
class LoggerWrapper:
    """Wrapper to handle different SourceIO logger versions"""
    def __init__(self, base_logger):
        self._logger = base_logger
    
    def info(self, msg):
        if hasattr(self._logger, 'info'):
            self._logger.info(msg)
        else:
            print(f"[INFO] {msg}")
    
    def warning(self, msg):
        # Some versions use 'warn' instead of 'warning'
        if hasattr(self._logger, 'warning'):
            self._logger.warning(msg)
        elif hasattr(self._logger, 'warn'):
            self._logger.warn(msg)
        else:
            print(f"[WARNING] {msg}")
    
    def error(self, msg):
        if hasattr(self._logger, 'error'):
            self._logger.error(msg)
        else:
            print(f"[ERROR] {msg}")
    
    def debug(self, msg):
        if hasattr(self._logger, 'debug'):
            self._logger.debug(msg)
        else:
            print(f"[DEBUG] {msg}")


# Check if SourceIO is available
SOURCEIO_AVAILABLE = False
try:
    from SourceIO.blender_bindings.operators.import_settings_base import ModelOptions
    from SourceIO.blender_bindings.operators.operator_helper import ImportOperatorHelper
    from SourceIO.blender_bindings.shared.exceptions import RequiredFileNotFound
    from SourceIO.blender_bindings.shared.model_container import ModelContainer
    from SourceIO.blender_bindings.utils.resource_utils import serialize_mounted_content, deserialize_mounted_content
    from SourceIO.blender_bindings.utils.bpy_utils import get_or_create_material
    from SourceIO.library.shared.content_manager import ContentManager
    from SourceIO.library.utils import FileBuffer
    from SourceIO.library.utils.tiny_path import TinyPath
    from SourceIO.library.models.mdl.v49 import MdlV49
    from SourceIO.library.models.vtx import open_vtx
    from SourceIO.library.models.vvd import Vvd
    from SourceIO.library.utils.path_utilities import find_vtx_cm
    from SourceIO.blender_bindings.models.common import put_into_collections
    from SourceIO.blender_bindings.models.mdl49.import_mdl import import_model as import_mdl49_model, import_animations
    from SourceIO.blender_bindings.source1.phy import import_physics
    from SourceIO.library.models.phy.phy import Phy
    from SourceIO.logger import SourceLogMan
    SOURCEIO_AVAILABLE = True
    _base_logger = SourceLogMan().get_logger("VLG::SourceIO")
    logger = LoggerWrapper(_base_logger)
except ImportError as e:
    print(f"[VLG] SourceIO not found - MDL import integration disabled: {e}")
    # Create a fallback logger that just prints
    class FallbackLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARNING] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def debug(self, msg): print(f"[DEBUG] {msg}")
    logger = FallbackLogger()


def import_materials_vlg(content_manager: ContentManager, mdl, base_path: str, fix_wetness: bool = False):
    """
    Import materials using our VLG shader instead of SourceIO's.
    This replaces SourceIO's import_materials function.
    
    Args:
        content_manager: SourceIO content manager
        mdl: MDL model data
        base_path: Base path for resolving textures
        fix_wetness: If True, reduces phong exponent scaling to prevent shiny/wet appearance
    """
    try:
        # Import our VLG module
        from . import parse_vmt, apply_vlg_material, VLGMaterialProperties, resolve_texture_path
    except ImportError:
        import sys
        # Get the parent module
        parent = sys.modules.get('blender_vertexlitgeneric')
        if parent:
            parse_vmt = parent.parse_vmt
            apply_vlg_material = parent.apply_vlg_material
            VLGMaterialProperties = parent.VLGMaterialProperties
            resolve_texture_path = parent.resolve_texture_path
        else:
            print("[VLG] Could not import VLG functions")
            return {}
    
    material_mapper = {}
    
    for material in mdl.materials:
        material_path = None
        material_file = None
        
        # Search through material paths to find the VMT
        vmt_disk_path = None  # Will store actual disk path if available
        for mat_path in mdl.materials_paths:
            vmt_path = TinyPath("materials") / mat_path / (material.name + ".vmt")
            material_file = content_manager.find_file(vmt_path)
            if material_file:
                material_path = TinyPath(mat_path) / material.name
                
                # Try multiple ways to get the actual disk path
                # Method 1: Direct path attribute
                vmt_disk_path = getattr(material_file, 'path', None)
                if vmt_disk_path:
                    vmt_disk_path = str(vmt_disk_path)
                
                # Method 2: Try filepath attribute
                if not vmt_disk_path:
                    vmt_disk_path = getattr(material_file, 'filepath', None)
                    if vmt_disk_path:
                        vmt_disk_path = str(vmt_disk_path)
                
                # Method 3: Try to construct from content manager's mounted paths
                if not vmt_disk_path:
                    # Check if it's a loose file by looking at the content provider
                    try:
                        # The material_file might have info about where it came from
                        if hasattr(material_file, '_path'):
                            vmt_disk_path = str(material_file._path)
                    except:
                        pass
                
                # Method 4: Search common game paths for this VMT
                if not vmt_disk_path:
                    import os
                    vmt_relative = str(vmt_path)
                    # Try base_path first (where MDL was loaded from)
                    if base_path:
                        # Go up to find garrysmod folder
                        test_base = base_path
                        for _ in range(10):  # Max 10 levels up
                            test_path = os.path.join(test_base, vmt_relative)
                            if os.path.exists(test_path):
                                vmt_disk_path = test_path
                                break
                            parent = os.path.dirname(test_base)
                            if parent == test_base:
                                break
                            test_base = parent
                
                logger.info(f"[VLG] Found VMT: {vmt_path}" + (f" (disk: {vmt_disk_path})" if vmt_disk_path else " (in VPK or path unknown)"))
                break
        
        if material_path is None:
            logger.warning(f"[VLG] Material {material.name} not found in any search path")
            # Create a stub material
            mat = bpy.data.materials.new(material.name)
            mat.use_nodes = True
            material_mapper[material.material_pointer] = mat
            continue
        
        # Get or create the Blender material
        mat = get_or_create_material(material.name, material_path.as_posix())
        material_mapper[material.material_pointer] = mat
        
        # Check if already loaded with VLG
        if mat.get('vlg_loaded', False):
            logger.info(f"[VLG] Skipping {mat.name} - already loaded")
            continue
        
        # Read the VMT content
        try:
            vmt_content = material_file.read().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"[VLG] Failed to read VMT for {material.name}: {e}")
            continue
        
        # Ensure material has nodes
        mat.use_nodes = True
        
        # Get VLG properties
        props = mat.vlg_props
        
        # Build base directory for texture resolution
        # The base_path is typically the directory containing the MDL
        vmt_dir = str(TinyPath("materials") / material_path.parent)
        
        # Parse VMT with content manager for texture resolution
        parse_vmt_with_cm(vmt_content, props, content_manager, vmt_dir, base_path)
        
        # Apply fix_wetness option from import dialog
        props.fix_wetness = fix_wetness
        
        # Debug: Log material properties before applying
        logger.info(f"[VLG] Material {material.name}: translucent={props.translucent}, alphatest={props.alphatest}, fix_wetness={props.fix_wetness}")
        
        # Apply our VLG shader
        try:
            apply_vlg_material(mat, props)
            mat['vlg_loaded'] = True
            # Store actual disk path if available, otherwise store relative path
            mat['vlg_vmt_path'] = vmt_disk_path if vmt_disk_path else str(vmt_path)
            
            # Ensure blend settings are correct for translucent/alphatest materials
            # Note: apply_vlg_material handles the blend mode based on $allowalphatocoverage
            if props.translucent or props.alphatest:
                logger.info(f"[VLG] Set blend_method for {material.name} (translucent={props.translucent})")
            
            # Apply correct color space and alpha settings for each texture type
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        node_name_lower = node.name.lower()
                        node_label_lower = node.label.lower() if node.label else ""
                        
                        # Base Texture: sRGB, Alpha Channel Packed
                        if 'basetexture' in node_name_lower or 'base' in node_label_lower:
                            node.image.colorspace_settings.name = 'sRGB'
                            node.image.alpha_mode = 'CHANNEL_PACKED'
                            logger.info(f"[VLG] Set {node.image.name} to sRGB, Alpha Channel Packed")
                        
                        # Normal Map: Non-Color, Alpha Channel Packed
                        elif 'bumpmap' in node_name_lower or 'normal' in node_label_lower:
                            node.image.colorspace_settings.name = 'Non-Color'
                            node.image.alpha_mode = 'CHANNEL_PACKED'
                            logger.info(f"[VLG] Set {node.image.name} to Non-Color, Alpha Channel Packed")
                        
                        # Phong Exponent Texture: Non-Color, Alpha Channel Packed
                        elif 'phongexponent' in node_name_lower or 'exponent' in node_label_lower:
                            node.image.colorspace_settings.name = 'Non-Color'
                            node.image.alpha_mode = 'CHANNEL_PACKED'
                            logger.info(f"[VLG] Set {node.image.name} to Non-Color, Alpha Channel Packed")
            
            logger.info(f"[VLG] Applied VLG shader to: {material.name}")
        except Exception as e:
            logger.error(f"[VLG] Failed to apply VLG shader to {material.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Store material mapper on MDL for skingroups
    mdl.material_mapper = material_mapper
    return material_mapper


def parse_vmt_with_cm(vmt_content: str, props, content_manager: ContentManager, vmt_dir: str, base_path: str):
    """
    Parse VMT content and resolve textures using SourceIO's content manager.
    Converts texture paths to actual file paths that Blender can load.
    """
    import re
    import os
    
    # Import VTF loading from our module
    try:
        from . import vtf_parser
    except ImportError:
        import vtf_parser
    
    # Import SourceIO's texture importer
    try:
        from SourceIO.blender_bindings.source1.vtf import import_texture as sourceio_import_texture
        HAS_SOURCEIO_VTF = True
    except ImportError:
        HAS_SOURCEIO_VTF = False
    
    def resolve_and_load_texture(texture_path: str, is_color_texture: bool = True) -> str:
        """Resolve a texture path and return a path Blender can load.
        
        Args:
            texture_path: The texture path from VMT
            is_color_texture: True for base textures (sRGB), False for data textures (Non-Color)
        """
        if not texture_path:
            return ""
        
        # Clean the path
        texture_path = texture_path.strip('"\'').replace('\\', '/').replace('//', '/')
        if texture_path.startswith('/'):
            texture_path = texture_path[1:]
        
        # Get just the texture name for checking existing images
        tex_name = texture_path.split('/')[-1]
        
        # First check if SourceIO already loaded this texture into Blender
        for img in bpy.data.images:
            img_name_lower = img.name.lower()
            if tex_name.lower() in img_name_lower or texture_path.lower().replace('/', '_') in img_name_lower:
                logger.info(f"[VLG] Found existing image: {img.name}")
                # Set correct color space and alpha mode
                img.colorspace_settings.name = 'sRGB' if is_color_texture else 'Non-Color'
                img.alpha_mode = 'CHANNEL_PACKED'
                # Return a special marker so we know to use this image directly
                return f"BLENDER_IMAGE:{img.name}"
        
        # Try to find the file on disk
        for ext in ['.tga', '.png', '.jpg', '.jpeg', '.dds', '.bmp']:
            full_path = f"materials/{texture_path}{ext}"
            tex_file = content_manager.find_file(TinyPath(full_path))
            if tex_file:
                try:
                    actual_path = get_file_path(tex_file)
                    if actual_path and os.path.exists(actual_path):
                        logger.info(f"[VLG] Found texture: {actual_path}")
                        return actual_path
                except:
                    pass
        
        # Try VTF format
        vtf_path = f"materials/{texture_path}.vtf"
        vtf_file = content_manager.find_file(TinyPath(vtf_path))
        if vtf_file:
            try:
                # First check if it's a real file on disk
                actual_path = get_file_path(vtf_file)
                if actual_path and os.path.exists(actual_path):
                    logger.info(f"[VLG] Found VTF: {actual_path}")
                    return actual_path
                
                # If it's in a VPK, use SourceIO's texture importer directly
                if HAS_SOURCEIO_VTF:
                    try:
                        # Use SourceIO's import_texture which handles VPK extraction properly
                        image = sourceio_import_texture(TinyPath(texture_path), vtf_file)
                        if image:
                            image.colorspace_settings.name = 'sRGB' if is_color_texture else 'Non-Color'
                            image.alpha_mode = 'CHANNEL_PACKED'
                            logger.info(f"[VLG] Loaded VTF via SourceIO: {image.name}")
                            return f"BLENDER_IMAGE:{image.name}"
                    except Exception as e:
                        logger.error(f"[VLG] SourceIO texture import failed: {e}")
                
                # Fallback: use our VTF parser
                vtf_data = vtf_file.read()
                if vtf_data:
                    try:
                        from io import BytesIO
                        safe_name = texture_path.replace('/', '_').replace('\\', '_')
                        image = vtf_parser.load_vtf_to_blender(BytesIO(vtf_data), safe_name)
                        if image:
                            image.colorspace_settings.name = 'sRGB' if is_color_texture else 'Non-Color'
                            image.alpha_mode = 'CHANNEL_PACKED'
                            logger.info(f"[VLG] Converted VTF: {image.name}")
                            return f"BLENDER_IMAGE:{image.name}"
                    except Exception as e:
                        logger.error(f"[VLG] Failed to convert VTF {texture_path}: {e}")
            except Exception as e:
                logger.error(f"[VLG] Error loading texture {texture_path}: {e}")
        
        logger.warning(f"[VLG] Texture not found: {texture_path}")
        return texture_path  # Return original path as fallback
    
    def get_file_path(file_obj) -> str:
        """Get the actual filesystem path from a SourceIO file object"""
        if hasattr(file_obj, 'name') and isinstance(file_obj.name, str):
            return file_obj.name
        if hasattr(file_obj, 'filepath'):
            return str(file_obj.filepath)
        if hasattr(file_obj, 'path'):
            return str(file_obj.path)
        if hasattr(file_obj, '_path'):
            return str(file_obj._path)
        return None
    
    # Parse the VMT line by line
    lines = vmt_content.split('\n')
    in_proxies = False
    brace_depth = 0
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('//'):
            continue
        
        # Track brace depth for proxy sections
        if '{' in line:
            brace_depth += line.count('{')
        if '}' in line:
            brace_depth -= line.count('}')
        
        # Check for proxies section
        if 'proxies' in line.lower():
            in_proxies = True
            continue
        
        # Skip proxy contents
        if in_proxies and brace_depth > 1:
            continue
        if in_proxies and brace_depth <= 1:
            in_proxies = False
        
        # Match key-value pairs: "$key" "value" or $key value
        # Note: \s* allows zero or more whitespace (some VMTs have no space like "$key""value")
        match = re.match(r'["\']?\$?(\w+)["\']?\s*["\']?([^"\']+)["\']?', line, re.IGNORECASE)
        if not match:
            continue
        
        key = match.group(1).lower()
        value = match.group(2).strip()
        
        # Handle texture paths (is_color_texture=True for sRGB, False for Non-Color data)
        if key == 'basetexture':
            props.basetexture = resolve_and_load_texture(value, is_color_texture=True)
        elif key == 'bumpmap':
            props.bumpmap = resolve_and_load_texture(value, is_color_texture=False)
        elif key == 'phongexponenttexture':
            props.phongexponenttexture = resolve_and_load_texture(value, is_color_texture=False)
        elif key == 'envmap':
            # Special envmap values
            if value.lower() in ('env_cubemap', 'environment maps/metal_generic_001'):
                props.envmap = value
            else:
                props.envmap = resolve_and_load_texture(value, is_color_texture=True)
        elif key == 'envmapmask':
            props.envmapmask = resolve_and_load_texture(value, is_color_texture=False)
        elif key == 'selfillummask':
            props.selfillummask = resolve_and_load_texture(value, is_color_texture=False)
        elif key == 'lightwarptexture':
            props.lightwarptexture = resolve_and_load_texture(value, is_color_texture=False)
        elif key == 'detail':
            props.detail = resolve_and_load_texture(value, is_color_texture=True)
        
        # Handle boolean properties
        elif key == 'phong':
            props.phong = value.lower() in ('1', 'true', 'yes')
        elif key == 'selfillum':
            props.selfillum = value.lower() in ('1', 'true', 'yes')
        elif key == 'translucent':
            props.translucent = value.lower() in ('1', 'true', 'yes')
            logger.info(f"[VLG] Parsed $translucent = {value} -> {props.translucent}")
        elif key == 'alphatest':
            props.alphatest = value.lower() in ('1', 'true', 'yes')
        elif key == 'nocull':
            props.nocull = value.lower() in ('1', 'true', 'yes')
        elif key == 'additive':
            props.additive = value.lower() in ('1', 'true', 'yes')
        elif key == 'rimlight':
            props.rimlight = value.lower() in ('1', 'true', 'yes')
        elif key == 'halflambert':
            props.halflambert = value.lower() in ('1', 'true', 'yes')
        elif key == 'phongalbedotint':
            props.phongalbedotint = value.lower() in ('1', 'true', 'yes')
        elif key == 'blendtintbybasealpha':
            props.blendtintbybasealpha = value.lower() in ('1', 'true', 'yes')
        elif key == 'basealphaenvmapmask':
            props.basealphaenvmapmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'normalmapalphaenvmapmask':
            props.normalmapalphaenvmapmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'basemapalphaphongmask':
            props.basemapalphaphongmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'normalmapalphaphongmask':
            props.normalmapalphaphongmask = value.lower() in ('1', 'true', 'yes')
        
        # Handle numeric properties
        elif key == 'phongexponent':
            try:
                props.phongexponent = float(value)
            except ValueError:
                pass
        elif key == 'phongboost':
            try:
                props.phongboost = float(value)
            except ValueError:
                pass
        elif key == 'rimlightexponent':
            try:
                props.rimlightexponent = float(value)
            except ValueError:
                pass
        elif key == 'rimlightboost':
            try:
                props.rimlightboost = float(value)
            except ValueError:
                pass
        elif key == 'envmapfresnel':
            try:
                props.envmapfresnel = float(value)
            except ValueError:
                pass
        elif key == 'envmapcontrast':
            try:
                props.envmapcontrast = float(value)
            except ValueError:
                pass
        elif key == 'envmapsaturation':
            try:
                props.envmapsaturation = float(value)
            except ValueError:
                pass
        elif key == 'alphatestreference':
            try:
                props.alphatestreference = float(value)
            except ValueError:
                pass
        elif key == 'allowalphatocoverage':
            props.allowalphatocoverage = value.lower() in ('1', 'true', 'yes')
        
        # Handle color/vector properties
        elif key == 'envmaptint':
            try:
                # Parse "[r g b]" format
                vec_match = re.match(r'\[?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]?', value)
                if vec_match:
                    props.envmaptint = (float(vec_match.group(1)), float(vec_match.group(2)), float(vec_match.group(3)))
            except:
                pass
        elif key == 'phongtint':
            try:
                vec_match = re.match(r'\[?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]?', value)
                if vec_match:
                    props.phongtint = (float(vec_match.group(1)), float(vec_match.group(2)), float(vec_match.group(3)))
            except:
                pass
        elif key == 'phongfresnelranges':
            try:
                vec_match = re.match(r'\[?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]?', value)
                if vec_match:
                    props.phongfresnelranges = (float(vec_match.group(1)), float(vec_match.group(2)), float(vec_match.group(3)))
            except:
                pass
        elif key == 'selfillumtint':
            try:
                vec_match = re.match(r'\[?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]?', value)
                if vec_match:
                    props.selfillumtint = (float(vec_match.group(1)), float(vec_match.group(2)), float(vec_match.group(3)))
            except:
                pass
        elif key == 'color' or key == 'color2':
            try:
                vec_match = re.match(r'\[?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]?', value)
                if vec_match:
                    color_val = (float(vec_match.group(1)), float(vec_match.group(2)), float(vec_match.group(3)))
                    if key == 'color':
                        props.color = color_val
                    else:
                        props.color2 = color_val
            except:
                pass


if SOURCEIO_AVAILABLE:
    
    class VLG_OT_SourceIO_MDLImport(ImportOperatorHelper, ModelOptions):
        """Load Source Engine MDL models with Softlamps VLG materials"""
        bl_idname = "vlg.sourceio_mdl"
        bl_label = "Import Source MDL (Softlamps VLG)"
        bl_options = {'UNDO'}

        discover_resources: BoolProperty(name="Mount discovered content", default=True)
        fix_wetness: BoolProperty(
            name="Fix Wetness",
            description="Reduces phong exponent scaling to prevent overly shiny/wet appearance",
            default=False
        )
        filter_glob: StringProperty(default="*.mdl;*.md3", options={'HIDDEN'})

        def execute(self, context):
            directory = self.get_directory()
            base_path = str(directory)

            content_manager = ContentManager()
            if self.discover_resources:
                content_manager.scan_for_content(directory)
                serialize_mounted_content(content_manager)
            else:
                deserialize_mounted_content(content_manager)

            for file in self.files:
                mdl_path = directory / file.name
                
                with FileBuffer(mdl_path) as f:
                    try:
                        # Load MDL file
                        mdl = MdlV49.from_buffer(f)
                        
                        # Find VTX and VVD files
                        vtx_buffer = find_vtx_cm(mdl_path, content_manager)
                        vvd_buffer = content_manager.find_file(mdl_path.with_suffix(".vvd"))
                        
                        if vtx_buffer is None or vvd_buffer is None:
                            self.report({"ERROR"}, f"Could not find VTX and/or VVD file for {mdl_path}")
                            return {'CANCELLED'}
                        
                        vtx = open_vtx(vtx_buffer)
                        vvd = Vvd.from_buffer(vvd_buffer)
                        
                        # Import materials with OUR VLG shader
                        if self.import_textures:
                            import_materials_vlg(content_manager, mdl, base_path, fix_wetness=self.fix_wetness)
                        
                        # Import the model geometry
                        container = import_mdl49_model(content_manager, mdl, vtx, vvd, 
                                                       self.scale, self.create_flex_drivers)
                        
                        # Import physics if requested
                        if self.import_physics:
                            phy_buffer = content_manager.find_file(mdl_path.with_suffix(".phy"))
                            if phy_buffer:
                                phy = Phy.from_buffer(phy_buffer)
                                import_physics(phy, phy_buffer, mdl, container, self.scale)
                        
                        # Import animations if requested
                        if self.import_animations and container.armature:
                            import_animations(content_manager, mdl, container.armature, self.scale)
                        
                    except RequiredFileNotFound as e:
                        self.report({"ERROR"}, e.message)
                        return {'CANCELLED'}
                    except Exception as e:
                        self.report({"ERROR"}, str(e))
                        import traceback
                        traceback.print_exc()
                        return {'CANCELLED'}

                # Put model into collections
                put_into_collections(container, mdl_path.stem, bodygroup_grouping=self.bodygroup_grouping)

            self.report({'INFO'}, f"Imported MDL with VLG materials")
            return {'FINISHED'}


def register_sourceio_integration():
    """Register SourceIO integration operators"""
    if SOURCEIO_AVAILABLE:
        try:
            bpy.utils.register_class(VLG_OT_SourceIO_MDLImport)
            print("[VLG] SourceIO integration registered")
        except Exception as e:
            print(f"[VLG] Failed to register SourceIO integration: {e}")


def unregister_sourceio_integration():
    """Unregister SourceIO integration operators"""
    if SOURCEIO_AVAILABLE:
        try:
            bpy.utils.unregister_class(VLG_OT_SourceIO_MDLImport)
        except:
            pass


def draw_sourceio_menu(self, context):
    """Add our operator to the import menu"""
    if SOURCEIO_AVAILABLE:
        self.layout.operator(VLG_OT_SourceIO_MDLImport.bl_idname, text="Source MDL (Softlamps VLG)")
