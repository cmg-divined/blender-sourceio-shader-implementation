# VertexLitGeneric Shader for Blender
# Recreation of Source Engine's VertexLitGeneric shader
# Compatible with Eevee and Cycles

bl_info = {
    "name": "VertexLitGeneric Shader",
    "author": "Source Engine Shader Recreation",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "Properties > Material > VertexLitGeneric",
    "description": "Recreates Source Engine's VertexLitGeneric shader with all parameters",
    "category": "Material",
}

import bpy
from bpy.props import (
    BoolProperty, FloatProperty, FloatVectorProperty,
    StringProperty, EnumProperty, IntProperty, PointerProperty
)
from bpy.types import PropertyGroup, Panel, Operator
import os
import re

# Import shader node builders (handles both package and direct execution)
try:
    from . import shader_nodes
    from . import vtf_parser
    from . import sourceio_integration
except ImportError:
    import shader_nodes
    import vtf_parser
    try:
        import sourceio_integration
    except ImportError:
        sourceio_integration = None


# ============================================================================
# PROPERTY GROUP - All VertexLitGeneric parameters
# ============================================================================

class VLGMaterialProperties(PropertyGroup):
    """Properties matching Source Engine's VertexLitGeneric shader"""
    
    # -------------------------------------------------------------------------
    # Core Textures
    # -------------------------------------------------------------------------
    basetexture: StringProperty(
        name="Base Texture",
        description="$basetexture - Primary diffuse/albedo texture",
        subtype='FILE_PATH',
        default=""
    )
    
    bumpmap: StringProperty(
        name="Normal Map",
        description="$bumpmap - Normal map texture for surface detail",
        subtype='FILE_PATH',
        default=""
    )
    
    # -------------------------------------------------------------------------
    # Color and Modulation
    # -------------------------------------------------------------------------
    color: FloatVectorProperty(
        name="Color",
        description="$color - Base color tint",
        subtype='COLOR',
        size=3,
        min=0.0, max=2.0,
        default=(1.0, 1.0, 1.0)
    )
    
    color2: FloatVectorProperty(
        name="Color2",
        description="$color2 - Secondary color tint (modulation)",
        subtype='COLOR',
        size=3,
        min=0.0, max=2.0,
        default=(1.0, 1.0, 1.0)
    )
    
    alpha: FloatProperty(
        name="Alpha",
        description="$alpha - Overall opacity",
        min=0.0, max=1.0,
        default=1.0
    )
    
    blendtintbybasealpha: BoolProperty(
        name="Blend Tint By Base Alpha",
        description="$blendtintbybasealpha - Use base texture alpha to blend color tint",
        default=False
    )
    
    blendtintcoloroverbase: FloatProperty(
        name="Blend Tint Color Over Base",
        description="$blendtintcoloroverbase - Blend between tint multiply and replace",
        min=0.0, max=1.0,
        default=0.0
    )
    
    # -------------------------------------------------------------------------
    # Phong Specular
    # -------------------------------------------------------------------------
    phong: BoolProperty(
        name="Phong",
        description="$phong - Enable Phong specular highlights",
        default=False
    )
    
    phongexponent: FloatProperty(
        name="Phong Exponent",
        description="$phongexponent - Sharpness of specular highlights",
        min=0.1, soft_max=150.0,
        default=20.0
    )
    
    phongboost: FloatProperty(
        name="Phong Boost",
        description="$phongboost - Intensity multiplier for specular",
        min=0.0, soft_max=10.0,
        default=1.0
    )
    
    phongfresnelranges: FloatVectorProperty(
        name="Phong Fresnel Ranges",
        description="$phongfresnelranges - [min, mid, max] fresnel remapping",
        size=3,
        min=0.0, soft_max=20.0,
        default=(0.0, 0.5, 1.0)
    )
    
    phongtint: FloatVectorProperty(
        name="Phong Tint",
        description="$phongtint - Color of specular highlights",
        subtype='COLOR',
        size=3,
        min=0.0, soft_max=2.0,
        default=(1.0, 1.0, 1.0)
    )
    
    phongalbedotint: BoolProperty(
        name="Phong Albedo Tint",
        description="$phongalbedotint - Tint specular by base texture color",
        default=False
    )
    
    phongalbedoboost: FloatProperty(
        name="Phong Albedo Boost",
        description="$phongalbedoboost - Boost factor for albedo tinted specular",
        min=0.0, soft_max=100.0,
        default=1.0
    )
    
    phongexponenttexture: StringProperty(
        name="Phong Exponent Texture",
        description="$phongexponenttexture - Texture controlling specular exponent per-pixel",
        subtype='FILE_PATH',
        default=""
    )
    
    basemapalphaphongmask: BoolProperty(
        name="Base Map Alpha Phong Mask",
        description="$basemapalphaphongmask - Use base texture alpha as phong mask",
        default=False
    )
    
    invertphongmask: BoolProperty(
        name="Invert Phong Mask",
        description="$invertphongmask - Invert the phong mask",
        default=False
    )
    
    phongdisablehalflambert: BoolProperty(
        name="Disable Half-Lambert",
        description="$phongdisablehalflambert - Disable half-lambert diffuse wrapping",
        default=False
    )
    
    # -------------------------------------------------------------------------
    # Light Warp
    # -------------------------------------------------------------------------
    lightwarptexture: StringProperty(
        name="Light Warp Texture",
        description="$lightwarptexture - 1D texture for diffuse lighting remap (toon shading)",
        subtype='FILE_PATH',
        default=""
    )
    
    phongwarptexture: StringProperty(
        name="Phong Warp Texture",
        description="$phongwarptexture - 2D texture for specular remapping",
        subtype='FILE_PATH',
        default=""
    )
    
    # -------------------------------------------------------------------------
    # Environment Map (Reflections)
    # -------------------------------------------------------------------------
    envmap: StringProperty(
        name="Environment Map",
        description="$envmap - Cubemap for reflections (use 'env_cubemap' for scene cubemap)",
        subtype='FILE_PATH',
        default=""
    )
    
    envmaptint: FloatVectorProperty(
        name="Envmap Tint",
        description="$envmaptint - Color tint for environment reflections",
        subtype='COLOR',
        size=3,
        min=0.0, soft_max=2.0,
        default=(1.0, 1.0, 1.0)
    )
    
    envmapcontrast: FloatProperty(
        name="Envmap Contrast",
        description="$envmapcontrast - Contrast of reflections (0=normal, 1=squared)",
        min=0.0, soft_max=1.0,
        default=0.0
    )
    
    envmapsaturation: FloatProperty(
        name="Envmap Saturation",
        description="$envmapsaturation - Saturation of reflections (0=grayscale, 1=full color)",
        min=0.0, soft_max=1.0,
        default=1.0
    )
    
    envmapfresnel: FloatProperty(
        name="Envmap Fresnel",
        description="$envmapfresnel - Fresnel effect strength for reflections",
        min=0.0, soft_max=1.0,
        default=0.0
    )
    
    envmapmask: StringProperty(
        name="Envmap Mask",
        description="$envmapmask - Texture controlling reflection intensity",
        subtype='FILE_PATH',
        default=""
    )
    
    basealphaenvmapmask: BoolProperty(
        name="Base Alpha Envmap Mask",
        description="$basealphaenvmapmask - Use base texture alpha as envmap mask",
        default=False
    )
    
    normalmapalphaenvmapmask: BoolProperty(
        name="Normal Map Alpha Envmap Mask",
        description="$normalmapalphaenvmapmask - Use normal map alpha as envmap mask",
        default=False
    )
    
    # -------------------------------------------------------------------------
    # Self-Illumination
    # -------------------------------------------------------------------------
    selfillum: BoolProperty(
        name="Self Illum",
        description="$selfillum - Enable self-illumination using base texture alpha",
        default=False
    )
    
    selfillumtint: FloatVectorProperty(
        name="Self Illum Tint",
        description="$selfillumtint - Color tint for self-illumination",
        subtype='COLOR',
        size=3,
        min=0.0, soft_max=2.0,
        default=(1.0, 1.0, 1.0)
    )
    
    selfillummask: StringProperty(
        name="Self Illum Mask",
        description="$selfillummask - Separate texture for self-illumination mask",
        subtype='FILE_PATH',
        default=""
    )
    
    selfillumfresnel: BoolProperty(
        name="Self Illum Fresnel",
        description="$selfillumfresnel - Apply fresnel to self-illumination",
        default=False
    )
    
    selfillumfresnelminmaxexp: FloatVectorProperty(
        name="Self Illum Fresnel MinMaxExp",
        description="$selfillumfresnelminmaxexp - [min, max, exponent] for fresnel",
        size=3,
        default=(0.0, 1.0, 1.0)
    )
    
    # -------------------------------------------------------------------------
    # Rim Lighting
    # -------------------------------------------------------------------------
    rimlight: BoolProperty(
        name="Rim Light",
        description="$rimlight - Enable rim lighting effect",
        default=False
    )
    
    rimlightexponent: FloatProperty(
        name="Rim Light Exponent",
        description="$rimlightexponent - Sharpness of rim light falloff",
        min=0.1, soft_max=100.0,
        default=4.0
    )
    
    rimlightboost: FloatProperty(
        name="Rim Light Boost",
        description="$rimlightboost - Intensity of rim light",
        min=0.0, soft_max=10.0,
        default=1.0
    )
    
    rimmask: BoolProperty(
        name="Rim Mask",
        description="$rimmask - Use phong exponent texture alpha as rim mask",
        default=False
    )
    
    # -------------------------------------------------------------------------
    # Detail Texture
    # -------------------------------------------------------------------------
    detail: StringProperty(
        name="Detail Texture",
        description="$detail - Detail texture for close-up surface variation",
        subtype='FILE_PATH',
        default=""
    )
    
    detailscale: FloatProperty(
        name="Detail Scale",
        description="$detailscale - UV scale for detail texture",
        min=0.01, soft_max=100.0,
        default=4.0
    )
    
    detailblendfactor: FloatProperty(
        name="Detail Blend Factor",
        description="$detailblendfactor - Intensity of detail texture",
        min=0.0, soft_max=1.0,
        default=1.0
    )
    
    detailblendmode: EnumProperty(
        name="Detail Blend Mode",
        description="$detailblendmode - How detail texture combines with base",
        items=[
            ('0', 'Mod2X', 'Multiply by 2 (detail gray = no change)'),
            ('1', 'Additive', 'Add detail to base'),
            ('2', 'Alpha Blend', 'Blend using detail alpha'),
            ('3', 'Crossfade', 'Linear blend'),
            ('4', 'Multiply', 'Straight multiply'),
            ('5', 'Add Self Illum', 'Add as self-illumination'),
            ('6', 'SSBump', 'Self-shadowed bump blend'),
        ],
        default='0'
    )
    
    detailtint: FloatVectorProperty(
        name="Detail Tint",
        description="$detailtint - Color tint for detail texture",
        subtype='COLOR',
        size=3,
        min=0.0, max=2.0,
        default=(1.0, 1.0, 1.0)
    )
    
    # -------------------------------------------------------------------------
    # Texture Transforms
    # -------------------------------------------------------------------------
    basetexturetransform_scale: FloatVectorProperty(
        name="Base Texture Scale",
        description="Scale for base texture UVs",
        size=2,
        default=(1.0, 1.0)
    )
    
    basetexturetransform_translate: FloatVectorProperty(
        name="Base Texture Offset",
        description="Offset for base texture UVs",
        size=2,
        default=(0.0, 0.0)
    )
    
    basetexturetransform_rotate: FloatProperty(
        name="Base Texture Rotation",
        description="Rotation for base texture UVs (degrees)",
        default=0.0
    )
    
    # -------------------------------------------------------------------------
    # Transparency
    # -------------------------------------------------------------------------
    translucent: BoolProperty(
        name="Translucent",
        description="$translucent - Enable alpha blending",
        default=False
    )
    
    alphatest: BoolProperty(
        name="Alpha Test",
        description="$alphatest - Enable alpha testing (cutout)",
        default=False
    )
    
    alphatestreference: FloatProperty(
        name="Alpha Test Reference",
        description="$alphatestreference - Alpha cutoff threshold",
        min=0.0, max=1.0,
        default=0.5
    )
    
    allowalphatocoverage: BoolProperty(
        name="Allow Alpha to Coverage",
        description="$allowalphatocoverage - Softer alpha edges (uses dithered transparency)",
        default=False
    )
    
    additive: BoolProperty(
        name="Additive",
        description="$additive - Additive blending mode",
        default=False
    )
    
    # -------------------------------------------------------------------------
    # Lighting
    # -------------------------------------------------------------------------
    halflambert: BoolProperty(
        name="Half-Lambert",
        description="$halflambert - Use half-lambert diffuse wrap",
        default=True
    )
    
    # -------------------------------------------------------------------------
    # Misc
    # -------------------------------------------------------------------------
    nocull: BoolProperty(
        name="No Cull",
        description="$nocull - Disable backface culling",
        default=False
    )
    
    fix_wetness: BoolProperty(
        name="Fix Wetness",
        description="Reduces phong exponent scaling to prevent overly shiny/wet appearance",
        default=False
    )
    
    model: BoolProperty(
        name="Model",
        description="$model - Material is for a model (affects lighting)",
        default=True
    )


# ============================================================================
# SHADER NODE BUILDER
# ============================================================================

def create_vlg_node_group():
    """Create or get the VertexLitGeneric node group"""
    
    group_name = "VertexLitGeneric"
    
    # Check if group already exists
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    # Create new node group
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Create group inputs/outputs
    group_inputs = group.nodes.new('NodeGroupInput')
    group_inputs.location = (-1200, 0)
    
    group_outputs = group.nodes.new('NodeGroupOutput')
    group_outputs.location = (800, 0)
    
    # Define inputs
    group.interface.new_socket(name="Base Color", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Base Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Normal", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Color Tint", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Phong Enabled", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Phong Exponent", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Phong Boost", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Phong Tint", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Phong Fresnel Min", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Phong Fresnel Mid", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Phong Fresnel Max", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Envmap Color", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Envmap Strength", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Envmap Fresnel", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Self Illum", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Self Illum Strength", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Rim Light Enabled", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Rim Light Exponent", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Rim Light Boost", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Half-Lambert", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Specular Mask", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    
    # Define outputs
    group.interface.new_socket(name="BSDF", in_out='OUTPUT', socket_type='NodeSocketShader')
    
    # -------------------------------------------------------------------------
    # Build the shader network
    # -------------------------------------------------------------------------
    
    # Geometry node for fresnel calculations
    geometry = group.nodes.new('ShaderNodeNewGeometry')
    geometry.location = (-1000, -200)
    
    # Camera data for view vector
    camera_data = group.nodes.new('ShaderNodeCameraData')
    camera_data.location = (-1000, -400)
    
    # Fresnel for rim lighting and envmap
    fresnel = group.nodes.new('ShaderNodeFresnel')
    fresnel.location = (-800, -300)
    
    # Principled BSDF as base
    principled = group.nodes.new('ShaderNodeBsdfPrincipled')
    principled.location = (200, 200)
    
    # Mix color tint with base
    mix_tint = group.nodes.new('ShaderNodeMix')
    mix_tint.data_type = 'RGBA'
    mix_tint.blend_type = 'MULTIPLY'
    mix_tint.location = (-400, 300)
    mix_tint.inputs['Factor'].default_value = 1.0
    
    # Convert phong exponent to roughness
    # Roughness = sqrt(2 / (phongExp + 2))
    phong_add = group.nodes.new('ShaderNodeMath')
    phong_add.operation = 'ADD'
    phong_add.location = (-600, -100)
    phong_add.inputs[1].default_value = 2.0
    
    phong_div = group.nodes.new('ShaderNodeMath')
    phong_div.operation = 'DIVIDE'
    phong_div.location = (-400, -100)
    phong_div.inputs[0].default_value = 2.0
    
    phong_sqrt = group.nodes.new('ShaderNodeMath')
    phong_sqrt.operation = 'SQRT'
    phong_sqrt.location = (-200, -100)
    
    # Rim lighting calculation
    rim_power = group.nodes.new('ShaderNodeMath')
    rim_power.operation = 'POWER'
    rim_power.location = (-600, -500)
    
    rim_invert = group.nodes.new('ShaderNodeMath')
    rim_invert.operation = 'SUBTRACT'
    rim_invert.location = (-800, -500)
    rim_invert.inputs[0].default_value = 1.0
    
    rim_multiply = group.nodes.new('ShaderNodeMath')
    rim_multiply.operation = 'MULTIPLY'
    rim_multiply.location = (-400, -500)
    
    rim_color = group.nodes.new('ShaderNodeEmission')
    rim_color.location = (-200, -500)
    
    # Self-illumination emission
    selfillum_emission = group.nodes.new('ShaderNodeEmission')
    selfillum_emission.location = (-200, -700)
    
    # Mix shaders for rim and self-illum
    add_shader1 = group.nodes.new('ShaderNodeAddShader')
    add_shader1.location = (400, 0)
    
    add_shader2 = group.nodes.new('ShaderNodeAddShader')
    add_shader2.location = (600, 0)
    
    # Connect nodes
    links = group.links
    
    # Base color path
    links.new(group_inputs.outputs['Base Color'], mix_tint.inputs['A'])
    links.new(group_inputs.outputs['Color Tint'], mix_tint.inputs['B'])
    links.new(mix_tint.outputs['Result'], principled.inputs['Base Color'])
    
    # Normal
    links.new(group_inputs.outputs['Normal'], principled.inputs['Normal'])
    
    # Phong to roughness conversion
    links.new(group_inputs.outputs['Phong Exponent'], phong_add.inputs[0])
    links.new(phong_add.outputs[0], phong_div.inputs[1])
    links.new(phong_div.outputs[0], phong_sqrt.inputs[0])
    links.new(phong_sqrt.outputs[0], principled.inputs['Roughness'])
    
    # Specular (phong boost affects this)
    links.new(group_inputs.outputs['Phong Boost'], principled.inputs['Specular IOR Level'])
    
    # Fresnel for rim
    links.new(geometry.outputs['Incoming'], fresnel.inputs['Normal'])
    links.new(group_inputs.outputs['Rim Light Exponent'], fresnel.inputs['IOR'])
    
    # Rim lighting
    links.new(fresnel.outputs[0], rim_invert.inputs[1])
    links.new(rim_invert.outputs[0], rim_power.inputs[0])
    links.new(group_inputs.outputs['Rim Light Exponent'], rim_power.inputs[1])
    links.new(rim_power.outputs[0], rim_multiply.inputs[0])
    links.new(group_inputs.outputs['Rim Light Boost'], rim_multiply.inputs[1])
    links.new(rim_multiply.outputs[0], rim_color.inputs['Strength'])
    links.new(group_inputs.outputs['Phong Tint'], rim_color.inputs['Color'])
    
    # Self-illumination
    links.new(group_inputs.outputs['Self Illum'], selfillum_emission.inputs['Color'])
    links.new(group_inputs.outputs['Self Illum Strength'], selfillum_emission.inputs['Strength'])
    
    # Combine shaders
    links.new(principled.outputs['BSDF'], add_shader1.inputs[0])
    links.new(rim_color.outputs['Emission'], add_shader1.inputs[1])
    links.new(add_shader1.outputs[0], add_shader2.inputs[0])
    links.new(selfillum_emission.outputs['Emission'], add_shader2.inputs[1])
    
    # Output
    links.new(add_shader2.outputs[0], group_outputs.inputs['BSDF'])
    
    return group


def load_texture(filepath, color_space='sRGB', alpha_mode='CHANNEL_PACKED'):
    """Load a texture from filepath, return image. Auto-converts VTF files.
    
    Args:
        filepath: Path to the texture file, or "BLENDER_IMAGE:name" for existing images
        color_space: Color space for the image ('sRGB' for color, 'Non-Color' for data)
        alpha_mode: How to handle alpha ('CHANNEL_PACKED', 'STRAIGHT', 'NONE')
    """
    if not filepath:
        print(f"  [LOAD] No filepath provided")
        return None
    
    # Check if this is a reference to an existing Blender image
    if filepath.startswith("BLENDER_IMAGE:"):
        image_name = filepath[14:]  # Remove "BLENDER_IMAGE:" prefix
        img = bpy.data.images.get(image_name)
        if img:
            # Ensure correct settings
            img.colorspace_settings.name = color_space
            img.alpha_mode = alpha_mode
            print(f"  [LOAD] Using existing Blender image: {img.name}")
            return img
        else:
            print(f"  [LOAD] Blender image not found: {image_name}")
            return None
    
    abs_path = bpy.path.abspath(filepath)
    
    # Check if it's a VTF file or if we need to find one
    vtf_path = None
    if abs_path.lower().endswith('.vtf'):
        vtf_path = abs_path
    elif not os.path.exists(abs_path):
        # Try adding .vtf extension
        potential_vtf = abs_path + '.vtf'
        if os.path.exists(potential_vtf):
            vtf_path = potential_vtf
        else:
            # Check without extension
            base_no_ext = os.path.splitext(abs_path)[0]
            if os.path.exists(base_no_ext + '.vtf'):
                vtf_path = base_no_ext + '.vtf'
    
    # If we found a VTF file, convert it directly to Blender image
    if vtf_path and os.path.exists(vtf_path):
        print(f"  [LOAD] Found VTF file: {vtf_path}")
        try:
            img = vtf_parser.load_vtf_as_blender_image(vtf_path, os.path.basename(vtf_path))
            if img:
                img.colorspace_settings.name = color_space
                img.alpha_mode = alpha_mode
                print(f"  [LOAD] VTF converted successfully: {img.name}")
                return img
            else:
                print(f"  [LOAD] VTF conversion failed")
        except Exception as e:
            print(f"  [LOAD] VTF conversion error: {e}")
            import traceback
            traceback.print_exc()
    
    # Check if file exists (for non-VTF files)
    if not os.path.exists(abs_path):
        print(f"  [LOAD] File not found: {abs_path}")
        return None
    
    print(f"  [LOAD] Loading texture: {abs_path}")
    
    # Check if image already loaded
    for img in bpy.data.images:
        try:
            if bpy.path.abspath(img.filepath) == abs_path:
                img.colorspace_settings.name = color_space
                img.alpha_mode = alpha_mode
                print(f"  [LOAD] Using cached image: {img.name}")
                return img
        except:
            pass
    
    # Load new image
    try:
        img = bpy.data.images.load(abs_path)
        img.colorspace_settings.name = color_space
        img.alpha_mode = alpha_mode
        print(f"  [LOAD] Loaded successfully: {img.name}")
        return img
    except Exception as e:
        print(f"  [LOAD] Failed to load: {e}")
        return None


def apply_vlg_material(material, props):
    """Apply VertexLitGeneric shader to a material - Source Engine accurate lighting
    
    Args:
        material: Blender material to modify
        props: VLGMaterialProperties with shader parameters
    """
    
    # Create all node groups on first use (deferred from registration)
    try:
        shader_nodes.create_all_vlg_node_groups()
    except Exception as e:
        print(f"Note: Could not create VLG node groups: {e}")
    
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    
    # Clear existing nodes
    nodes.clear()
    
    # Create output node
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (1400, 0)
    
    # =========================================================================
    # SOURCE ENGINE LIGHTING MODEL
    # =========================================================================
    # Source Engine separates:
    #   1. Diffuse lighting (Lambert or Half-Lambert)
    #   2. Phong specular highlights (from lights only - NOT environment)
    #   3. Environment reflections (ONLY with $envmap, additive)
    #
    # Blender's Principled BSDF combines specular highlights and env reflections.
    # Our approach:
    #   - WITHOUT $envmap: High roughness to blur env reflections, keep light specular
    #   - WITH $envmap: Normal roughness + manual additive envmap sampling
    # =========================================================================
    
    has_envmap = bool(props.envmap)
    print(f"[SHADER] Building Source Engine lighting model (envmap: {has_envmap})")
    
    # Create Principled BSDF as the main shader
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    principled.location = (600, 100)
    principled.label = "Source Lit"
    
    # Configure based on envmap presence
    if has_envmap:
        # With envmap: Use normal phong-to-roughness conversion
        # Envmap will be added separately as emission
        if props.phong:
            roughness = (2.0 / (props.phongexponent + 2.0)) ** 0.5
            principled.inputs['Roughness'].default_value = roughness
            principled.inputs['Specular IOR Level'].default_value = props.phongboost * 0.4
        else:
            principled.inputs['Roughness'].default_value = 0.8
            principled.inputs['Specular IOR Level'].default_value = 0.2
        print(f"[SHADER] Envmap enabled - using phong roughness for light specular")
    else:
        # WITHOUT envmap: Allow phong specular from lights
        # Source shows specular highlights even without envmap
        # We allow lower roughness for specular, but reduce Specular IOR to minimize env reflections
        if props.phong:
            # Use the proper phong-to-roughness conversion
            roughness = (2.0 / (props.phongexponent + 2.0)) ** 0.5
            principled.inputs['Roughness'].default_value = roughness
            # Reduce specular IOR to minimize environment reflections
            # But keep enough for light specular highlights
            principled.inputs['Specular IOR Level'].default_value = props.phongboost * 0.25
        else:
            principled.inputs['Roughness'].default_value = 0.9
            principled.inputs['Specular IOR Level'].default_value = 0.1
        print(f"[SHADER] No envmap - using phong roughness ({principled.inputs['Roughness'].default_value:.2f}) with reduced specular IOR")
    
    # Disable metallic (Source phong isn't metallic)
    principled.inputs['Metallic'].default_value = 0.0
    
    # -------------------------------------------------------------------------
    # $phongalbedotint - Tint specular by base texture color
    # -------------------------------------------------------------------------
    if props.phongalbedotint:
        # Specular Tint controls the color of specular reflections
        # In Blender 4.x+, this is a color input (RGB)
        # Setting it to the base color tints specular by the texture
        if 'Specular Tint' in principled.inputs:
            # Specular Tint is a color in Blender 4.x/5.x
            # We'll connect it to the base texture later if available
            # For now, set a neutral tint that will be multiplied
            principled.inputs['Specular Tint'].default_value = (1.0, 1.0, 1.0, 1.0)
            print(f"[SHADER] Phong albedo tint enabled - will connect to base texture")
    
    # -------------------------------------------------------------------------
    # $phongfresnelranges - Modulate specular based on viewing angle
    # -------------------------------------------------------------------------
    # Implementation based on SourceIO's node group (reverse-engineered).
    # Uses piecewise linear interpolation:
    #   f = (1 - N·V)²
    #   When f < 0.5: result = mix(min, mid, f * 2)
    #   When f >= 0.5: result = mix(mid, max, f * 2 - 1)
    # -------------------------------------------------------------------------
    phong_fresnel_ranges = props.phongfresnelranges
    use_fresnel_ranges = props.phong and (phong_fresnel_ranges[0] != 0.0 or 
                                           phong_fresnel_ranges[1] != 0.5 or 
                                           phong_fresnel_ranges[2] != 1.0)
    
    if use_fresnel_ranges:
        print(f"[SHADER] Applying $phongfresnelranges: {phong_fresnel_ranges}")
        fr_min, fr_mid, fr_max = phong_fresnel_ranges
        
        # Get base specular value that was set earlier
        base_spec = principled.inputs['Specular IOR Level'].default_value
        
        # Geometry node for N·V calculation
        fr_geometry = nodes.new('ShaderNodeNewGeometry')
        fr_geometry.location = (200, 400)
        fr_geometry.label = "Fresnel Geometry"
        
        # Vector Math: DOT_PRODUCT(Normal, Incoming) = N·V
        fr_dot = nodes.new('ShaderNodeVectorMath')
        fr_dot.operation = 'DOT_PRODUCT'
        fr_dot.location = (400, 400)
        fr_dot.label = "N·V"
        links.new(fr_geometry.outputs['Normal'], fr_dot.inputs[0])
        links.new(fr_geometry.outputs['Incoming'], fr_dot.inputs[1])
        
        # Math.005: f = 1 - N·V
        fr_one_minus = nodes.new('ShaderNodeMath')
        fr_one_minus.operation = 'SUBTRACT'
        fr_one_minus.location = (550, 400)
        fr_one_minus.inputs[0].default_value = 1.0
        fr_one_minus.label = "1 - N·V"
        links.new(fr_dot.outputs['Value'], fr_one_minus.inputs[1])
        
        # Math.022: f² = f * f
        fr_square = nodes.new('ShaderNodeMath')
        fr_square.operation = 'MULTIPLY'
        fr_square.location = (700, 400)
        fr_square.label = "f²"
        links.new(fr_one_minus.outputs['Value'], fr_square.inputs[0])
        links.new(fr_one_minus.outputs['Value'], fr_square.inputs[1])
        
        # Math.023: factor_low = f² * 2 (remaps 0-0.5 to 0-1)
        fr_factor_low = nodes.new('ShaderNodeMath')
        fr_factor_low.operation = 'MULTIPLY'
        fr_factor_low.location = (850, 450)
        fr_factor_low.inputs[1].default_value = 2.0
        fr_factor_low.label = "f² × 2"
        links.new(fr_square.outputs['Value'], fr_factor_low.inputs[0])
        
        # Math.024: factor_high = f² * 2 - 1 (remaps 0.5-1 to 0-1)
        fr_factor_high = nodes.new('ShaderNodeMath')
        fr_factor_high.operation = 'ADD'
        fr_factor_high.location = (1000, 450)
        fr_factor_high.inputs[1].default_value = -1.0
        fr_factor_high.label = "f²×2 - 1"
        links.new(fr_factor_low.outputs['Value'], fr_factor_high.inputs[0])
        
        # Math.026: step = f² > 0.5 (1 when in high range, 0 when in low range)
        fr_step = nodes.new('ShaderNodeMath')
        fr_step.operation = 'GREATER_THAN'
        fr_step.location = (850, 300)
        fr_step.inputs[1].default_value = 0.5
        fr_step.label = "f² > 0.5"
        links.new(fr_square.outputs['Value'], fr_step.inputs[0])
        
        # Math.025: inv_step = 1 - step
        fr_inv_step = nodes.new('ShaderNodeMath')
        fr_inv_step.operation = 'SUBTRACT'
        fr_inv_step.location = (1000, 300)
        fr_inv_step.inputs[0].default_value = 1.0
        fr_inv_step.label = "1 - step"
        links.new(fr_step.outputs['Value'], fr_inv_step.inputs[1])
        
        # Mix.005: low_range = mix(min, mid, factor_low)
        fr_mix_low = nodes.new('ShaderNodeMix')
        fr_mix_low.data_type = 'FLOAT'
        fr_mix_low.location = (1150, 500)
        fr_mix_low.label = "Mix min→mid"
        fr_mix_low.inputs['A'].default_value = fr_min
        fr_mix_low.inputs['B'].default_value = fr_mid
        links.new(fr_factor_low.outputs['Value'], fr_mix_low.inputs['Factor'])
        
        # Mix.002: high_range = mix(mid, max, factor_high)
        fr_mix_high = nodes.new('ShaderNodeMix')
        fr_mix_high.data_type = 'FLOAT'
        fr_mix_high.location = (1150, 350)
        fr_mix_high.label = "Mix mid→max"
        fr_mix_high.inputs['A'].default_value = fr_mid
        fr_mix_high.inputs['B'].default_value = fr_max
        links.new(fr_factor_high.outputs['Value'], fr_mix_high.inputs['Factor'])
        
        # Math.027: low_contribution = low_range * inv_step
        fr_low_contrib = nodes.new('ShaderNodeMath')
        fr_low_contrib.operation = 'MULTIPLY'
        fr_low_contrib.location = (1300, 500)
        fr_low_contrib.label = "Low × mask"
        links.new(fr_mix_low.outputs['Result'], fr_low_contrib.inputs[0])
        links.new(fr_inv_step.outputs['Value'], fr_low_contrib.inputs[1])
        
        # Math.029: high_contribution = high_range * step
        fr_high_contrib = nodes.new('ShaderNodeMath')
        fr_high_contrib.operation = 'MULTIPLY'
        fr_high_contrib.location = (1300, 350)
        fr_high_contrib.label = "High × mask"
        links.new(fr_mix_high.outputs['Result'], fr_high_contrib.inputs[0])
        links.new(fr_step.outputs['Value'], fr_high_contrib.inputs[1])
        
        # Math.028: fresnel_result = low_contribution + high_contribution
        fr_result = nodes.new('ShaderNodeMath')
        fr_result.operation = 'ADD'
        fr_result.location = (1450, 420)
        fr_result.label = "Fresnel Ranges"
        links.new(fr_low_contrib.outputs['Value'], fr_result.inputs[0])
        links.new(fr_high_contrib.outputs['Value'], fr_result.inputs[1])
        
        # Multiply base specular by fresnel ranges result
        fr_spec_mult = nodes.new('ShaderNodeMath')
        fr_spec_mult.operation = 'MULTIPLY'
        fr_spec_mult.location = (1600, 420)
        fr_spec_mult.inputs[0].default_value = base_spec
        fr_spec_mult.label = "Spec × Fresnel"
        links.new(fr_result.outputs['Value'], fr_spec_mult.inputs[1])
        
        # Connect to Specular IOR Level
        links.new(fr_spec_mult.outputs['Value'], principled.inputs['Specular IOR Level'])
    
    # We'll use emission for self-illum effects
    emission = nodes.new('ShaderNodeEmission')
    emission.location = (600, -300)
    emission.inputs['Strength'].default_value = 0.0  # Disabled by default
    
    # Add shader to combine principled and emission (self-illum)
    add_shader = nodes.new('ShaderNodeAddShader')
    add_shader.location = (800, 0)
    add_shader.label = "Lit + SelfIllum"
    
    # Connect principled to add shader
    links.new(principled.outputs['BSDF'], add_shader.inputs[0])
    links.new(emission.outputs['Emission'], add_shader.inputs[1])
    
    # Current shader output (will be modified if envmap/transparency is added)
    current_shader = add_shader.outputs['Shader']
    
    # Mix shader for transparency (created now, connected later if needed)
    mix_shader = nodes.new('ShaderNodeMixShader')
    mix_shader.location = (1200, 0)
    mix_shader.label = "Transparency Mix"
    
    # Transparent shader
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    transparent.location = (1000, -150)
    
    # Current Y position for texture nodes
    tex_y = 600
    tex_x = -600
    
    # Track texture nodes for later reference (envmap masking, etc.)
    base_tex_node = None
    normal_tex_node = None
    envmap_shader = None
    envmap_factor = None
    normal_map_node = None  # Track for envmap reflection calculation
    
    # -------------------------------------------------------------------------
    # BASE TEXTURE
    # -------------------------------------------------------------------------
    base_color = props.color[:]
    base_alpha = props.alpha
    
    if props.basetexture:
        img = load_texture(props.basetexture, 'sRGB')
        if img:
            base_tex = nodes.new('ShaderNodeTexImage')
            base_tex.location = (tex_x, tex_y)
            base_tex.image = img
            base_tex.label = "Base Texture"
            base_tex_node = base_tex  # Track for envmap masking
            
            # UV node with transform
            uv_node = nodes.new('ShaderNodeUVMap')
            uv_node.location = (tex_x - 400, tex_y)
            
            # Mapping node for transforms
            mapping = nodes.new('ShaderNodeMapping')
            mapping.location = (tex_x - 200, tex_y)
            mapping.inputs['Scale'].default_value = (
                props.basetexturetransform_scale[0],
                props.basetexturetransform_scale[1],
                1.0
            )
            mapping.inputs['Location'].default_value = (
                props.basetexturetransform_translate[0],
                props.basetexturetransform_translate[1],
                0.0
            )
            mapping.inputs['Rotation'].default_value = (
                0.0, 0.0,
                props.basetexturetransform_rotate * 3.14159 / 180.0
            )
            
            links.new(uv_node.outputs['UV'], mapping.inputs['Vector'])
            links.new(mapping.outputs['Vector'], base_tex.inputs['Vector'])
            
            # Color tint mixing
            if props.blendtintbybasealpha:
                # Blend tint based on base alpha
                mix_tint = nodes.new('ShaderNodeMix')
                mix_tint.data_type = 'RGBA'
                mix_tint.location = (tex_x + 300, tex_y)
                
                tinted = nodes.new('ShaderNodeMix')
                tinted.data_type = 'RGBA'
                tinted.blend_type = 'MULTIPLY'
                tinted.location = (tex_x + 150, tex_y - 100)
                tinted.inputs['Factor'].default_value = 1.0
                
                links.new(base_tex.outputs['Color'], tinted.inputs['A'])
                tinted.inputs['B'].default_value = (*props.color2, 1.0)
                
                links.new(base_tex.outputs['Alpha'], mix_tint.inputs['Factor'])
                links.new(base_tex.outputs['Color'], mix_tint.inputs['A'])
                links.new(tinted.outputs['Result'], mix_tint.inputs['B'])
                links.new(mix_tint.outputs['Result'], principled.inputs['Base Color'])
            else:
                # Simple color multiplication
                mix_color = nodes.new('ShaderNodeMix')
                mix_color.data_type = 'RGBA'
                mix_color.blend_type = 'MULTIPLY'
                mix_color.location = (tex_x + 300, tex_y)
                mix_color.inputs['Factor'].default_value = 1.0
                mix_color.inputs['B'].default_value = (*props.color2, 1.0)
                
                links.new(base_tex.outputs['Color'], mix_color.inputs['A'])
                links.new(mix_color.outputs['Result'], principled.inputs['Base Color'])
            
            # $phongalbedotint - connect base texture to Specular Tint
            if props.phongalbedotint and 'Specular Tint' in principled.inputs:
                # Apply gamma correction like SourceIO does (0.4545 = 1/2.2)
                gamma_node = nodes.new('ShaderNodeGamma')
                gamma_node.location = (tex_x + 400, tex_y - 150)
                gamma_node.inputs['Gamma'].default_value = 0.4545
                gamma_node.label = "Albedo Tint Gamma"
                links.new(base_tex.outputs['Color'], gamma_node.inputs['Color'])
                links.new(gamma_node.outputs['Color'], principled.inputs['Specular Tint'])
                print(f"[SHADER] Connected base texture to Specular Tint (phongalbedotint)")
            
            tex_y -= 300
        else:
            principled.inputs['Base Color'].default_value = (*base_color, 1.0)
    else:
        principled.inputs['Base Color'].default_value = (*base_color, 1.0)
    
    # -------------------------------------------------------------------------
    # NORMAL MAP
    # -------------------------------------------------------------------------
    if props.bumpmap:
        img = load_texture(props.bumpmap, 'Non-Color')
        if img:
            bump_tex = nodes.new('ShaderNodeTexImage')
            bump_tex.location = (tex_x, tex_y)
            bump_tex.image = img
            bump_tex.label = "Normal Map"
            normal_tex_node = bump_tex  # Track for envmap masking
            
            normal_map = nodes.new('ShaderNodeNormalMap')
            normal_map.location = (tex_x + 300, tex_y)
            normal_map_node = normal_map  # Track for envmap reflections
            
            links.new(bump_tex.outputs['Color'], normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
            
            tex_y -= 300
    
    # -------------------------------------------------------------------------
    # LIGHTWARP TEXTURE (SourceIO-accurate implementation)
    # $lightwarptexture - 1D texture that remaps diffuse lighting
    # 
    # SourceIO approach:
    # 1. Create Diffuse BSDF with normal map
    # 2. Shader to RGB captures actual lighting intensity
    # 3. Map Range converts lighting (0-1) to UV (0-0.995)
    # 4. Sample lightwarp texture using lighting as X coordinate
    # 5. Overlay blend with shading result
    # -------------------------------------------------------------------------
    lightwarp_color_node = None
    if props.lightwarptexture:
        img = load_texture(props.lightwarptexture, 'sRGB')
        if img:
            print(f"[SHADER] Applying lightwarp texture (SourceIO method): {props.lightwarptexture}")
            
            # Create lightwarp texture node
            warp_tex = nodes.new('ShaderNodeTexImage')
            warp_tex.location = (tex_x, tex_y)
            warp_tex.image = img
            warp_tex.label = "Light Warp"
            warp_tex.interpolation = 'Linear'
            warp_tex.extension = 'EXTEND'  # Clamp to edge
            
            # Create a Diffuse BSDF to capture actual lighting (like SourceIO)
            lw_diffuse = nodes.new('ShaderNodeBsdfDiffuse')
            lw_diffuse.location = (tex_x - 400, tex_y - 100)
            lw_diffuse.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            lw_diffuse.inputs['Roughness'].default_value = 0.0
            lw_diffuse.label = "LW Diffuse"
            
            # Connect normal map if we have one
            if normal_map_node:
                links.new(normal_map_node.outputs['Normal'], lw_diffuse.inputs['Normal'])
            
            # Shader to RGB - captures actual lighting from scene
            lw_shader_to_rgb = nodes.new('ShaderNodeShaderToRGB')
            lw_shader_to_rgb.location = (tex_x - 200, tex_y - 100)
            lw_shader_to_rgb.label = "Lighting Capture"
            links.new(lw_diffuse.outputs['BSDF'], lw_shader_to_rgb.inputs['Shader'])
            
            # Map Range: lighting (0-1) → UV (0-0.995)
            # The 0.995 prevents sampling exactly at the edge
            lw_map_range = nodes.new('ShaderNodeMapRange')
            lw_map_range.location = (tex_x, tex_y - 100)
            lw_map_range.clamp = True
            lw_map_range.inputs['From Min'].default_value = 0.0
            lw_map_range.inputs['From Max'].default_value = 1.0
            lw_map_range.inputs['To Min'].default_value = 0.0
            lw_map_range.inputs['To Max'].default_value = 0.995
            lw_map_range.label = "Light→UV"
            links.new(lw_shader_to_rgb.outputs['Color'], lw_map_range.inputs['Value'])
            
            # Combine XYZ: X = lighting UV, Y = 0.5 (center of 1D texture)
            lw_combine_uv = nodes.new('ShaderNodeCombineXYZ')
            lw_combine_uv.location = (tex_x + 200, tex_y - 100)
            lw_combine_uv.inputs['Y'].default_value = 0.5
            lw_combine_uv.inputs['Z'].default_value = 0.0
            lw_combine_uv.label = "Warp UV"
            links.new(lw_map_range.outputs['Result'], lw_combine_uv.inputs['X'])
            
            # Connect UV to warp texture
            links.new(lw_combine_uv.outputs['Vector'], warp_tex.inputs['Vector'])
            
            # Store for later use in overlay blending
            lightwarp_color_node = warp_tex
            
            print(f"[SHADER] Lightwarp configured - samples based on actual scene lighting")
            tex_y -= 350
    
    # -------------------------------------------------------------------------
    # PHONG EXPONENT TEXTURE
    # Controls roughness per-pixel (R channel = exponent, higher = shinier)
    # -------------------------------------------------------------------------
    phong_tex_node = None
    if props.phongexponenttexture:
        img = load_texture(props.phongexponenttexture, 'Non-Color')
        if img:
            phong_tex = nodes.new('ShaderNodeTexImage')
            phong_tex.location = (tex_x, tex_y)
            phong_tex.image = img
            phong_tex.label = "Phong Exponent"
            phong_tex_node = phong_tex
            
            # Convert texture exponent to roughness: roughness = sqrt(2 / (exp + 2))
            # Texture R channel: 0=rough, 1=shiny (maps to exponent 1-150)
            sep_rgb = nodes.new('ShaderNodeSeparateColor')
            sep_rgb.location = (tex_x + 200, tex_y)
            links.new(phong_tex.outputs['Color'], sep_rgb.inputs['Color'])
            
            # Scale to exponent range
            # Normal: 149 (maps 0-1 to 1-150 exponent range)
            # Fix Wetness: 2 (much lower scaling, reduces shiny/wet look)
            exp_scale = nodes.new('ShaderNodeMath')
            exp_scale.operation = 'MULTIPLY'
            exp_scale.location = (tex_x + 350, tex_y)
            exp_scale.inputs[1].default_value = 2.0 if props.fix_wetness else 149.0
            exp_scale.label = "Exp Scale" + (" (Fixed)" if props.fix_wetness else "")
            links.new(sep_rgb.outputs['Red'], exp_scale.inputs[0])
            
            exp_add = nodes.new('ShaderNodeMath')
            exp_add.operation = 'ADD'
            exp_add.location = (tex_x + 500, tex_y)
            exp_add.inputs[1].default_value = 1.0
            links.new(exp_scale.outputs[0], exp_add.inputs[0])
            
            # roughness = sqrt(2 / (exp + 2))
            exp_plus2 = nodes.new('ShaderNodeMath')
            exp_plus2.operation = 'ADD'
            exp_plus2.location = (tex_x + 650, tex_y)
            exp_plus2.inputs[1].default_value = 2.0
            links.new(exp_add.outputs[0], exp_plus2.inputs[0])
            
            div_node = nodes.new('ShaderNodeMath')
            div_node.operation = 'DIVIDE'
            div_node.location = (tex_x + 800, tex_y)
            div_node.inputs[0].default_value = 2.0
            links.new(exp_plus2.outputs[0], div_node.inputs[1])
            
            sqrt_node = nodes.new('ShaderNodeMath')
            sqrt_node.operation = 'SQRT'
            sqrt_node.location = (tex_x + 950, tex_y)
            links.new(div_node.outputs[0], sqrt_node.inputs[0])
            
            # Connect roughness directly - allow full range for proper specular
            # The reduced Specular IOR Level (set above) handles env reflection reduction
            links.new(sqrt_node.outputs[0], principled.inputs['Roughness'])
            
            tex_y -= 300
    
    # -------------------------------------------------------------------------
    # ENVIRONMENT MAP (Source Engine Cubemap Reflections)
    # -------------------------------------------------------------------------
    # Source Engine envmap is ADDITIVE and SEPARATE from diffuse lighting.
    # It ONLY appears when $envmap is specified in the VMT.
    # We implement this using manual environment texture sampling + Emission
    # -------------------------------------------------------------------------
    envmap_enabled = False
    envmap_image = None
    envmap_factor_output = None
    
    if props.envmap:
        print(f"[ENVMAP] Envmap specified: {props.envmap}")
        envmap_enabled = True
        
        # Try to load the envmap texture
        # Special case: "env_cubemap" means use scene environment (no texture needed)
        if props.envmap.lower() not in ('env_cubemap', 'environment maps/metal_generic_001'):
            envmap_image = load_texture(props.envmap, 'sRGB')
            if envmap_image:
                print(f"[ENVMAP] Loaded envmap texture: {envmap_image.name}")
            else:
                print(f"[ENVMAP] Could not load envmap texture, will check for world environment")
        else:
            print(f"[ENVMAP] Using scene environment (env_cubemap)")
        
        # Source Engine envmap is ADDITIVE - it adds reflections on top of diffuse
        # The tint controls the reflection color AND intensity.
        
        tint_color = props.envmaptint[:]
        tint_brightness = max(tint_color[0], tint_color[1], tint_color[2])
        
        # Start building the envmap strength multiplier chain
        # Base strength from tint brightness
        envmap_strength = nodes.new('ShaderNodeValue')
        envmap_strength.location = (tex_x, tex_y - 100)
        envmap_strength.outputs[0].default_value = tint_brightness
        envmap_strength.label = "Envmap Base Strength"
        
        current_strength_output = envmap_strength.outputs[0]
        
        # Envmap mask handling
        if props.envmapmask:
            img = load_texture(props.envmapmask, 'Non-Color')
            if img:
                envmap_mask_tex = nodes.new('ShaderNodeTexImage')
                envmap_mask_tex.location = (tex_x, tex_y - 200)
                envmap_mask_tex.image = img
                envmap_mask_tex.label = "Envmap Mask"
                
                mask_mult = nodes.new('ShaderNodeMath')
                mask_mult.operation = 'MULTIPLY'
                mask_mult.location = (tex_x + 200, tex_y - 150)
                links.new(current_strength_output, mask_mult.inputs[0])
                links.new(envmap_mask_tex.outputs['Color'], mask_mult.inputs[1])
                current_strength_output = mask_mult.outputs[0]
                tex_y -= 100
        elif props.basealphaenvmapmask and base_tex_node:
            mask_mult = nodes.new('ShaderNodeMath')
            mask_mult.operation = 'MULTIPLY'
            mask_mult.location = (tex_x + 200, tex_y - 150)
            links.new(current_strength_output, mask_mult.inputs[0])
            links.new(base_tex_node.outputs['Alpha'], mask_mult.inputs[1])
            current_strength_output = mask_mult.outputs[0]
        elif props.normalmapalphaenvmapmask and normal_tex_node:
            mask_mult = nodes.new('ShaderNodeMath')
            mask_mult.operation = 'MULTIPLY'
            mask_mult.location = (tex_x + 200, tex_y - 150)
            links.new(current_strength_output, mask_mult.inputs[0])
            links.new(normal_tex_node.outputs['Alpha'], mask_mult.inputs[1])
            current_strength_output = mask_mult.outputs[0]
        
        # Fresnel for envmap (edge reflections stronger)
        if props.envmapfresnel > 0:
            envmap_fresnel = nodes.new('ShaderNodeFresnel')
            envmap_fresnel.location = (tex_x + 200, tex_y - 50)
            envmap_fresnel.inputs['IOR'].default_value = 1.0 + props.envmapfresnel
            
            fresnel_mult = nodes.new('ShaderNodeMath')
            fresnel_mult.operation = 'MULTIPLY'
            fresnel_mult.location = (tex_x + 350, tex_y - 100)
            links.new(current_strength_output, fresnel_mult.inputs[0])
            links.new(envmap_fresnel.outputs['Fac'], fresnel_mult.inputs[1])
            current_strength_output = fresnel_mult.outputs[0]
        
        # Contrast (Source: lerp between color and color*color)
        # Higher contrast = more squared = darker midtones, brighter highlights
        if props.envmapcontrast > 0:
            contrast_node = nodes.new('ShaderNodeMath')
            contrast_node.operation = 'POWER'
            contrast_node.location = (tex_x + 500, tex_y - 100)
            links.new(current_strength_output, contrast_node.inputs[0])
            contrast_node.inputs[1].default_value = 1.0 + props.envmapcontrast
            current_strength_output = contrast_node.outputs[0]
        
        # Clamp the final strength
        clamp_node = nodes.new('ShaderNodeClamp')
        clamp_node.location = (tex_x + 650, tex_y - 100)
        clamp_node.inputs['Min'].default_value = 0.0
        clamp_node.inputs['Max'].default_value = 1.0
        links.new(current_strength_output, clamp_node.inputs['Value'])
        
        envmap_factor_output = clamp_node.outputs[0]
        
        tex_y -= 300
    
    # -------------------------------------------------------------------------
    # SELF-ILLUMINATION
    # -------------------------------------------------------------------------
    if props.selfillum:
        emission_strength = 1.0
        emission_color = props.selfillumtint[:]
        
        if props.selfillummask:
            img = load_texture(props.selfillummask, 'Non-Color')
            if img:
                illum_tex = nodes.new('ShaderNodeTexImage')
                illum_tex.location = (tex_x, tex_y)
                illum_tex.image = img
                illum_tex.label = "Self Illum Mask"
                
                illum_mix = nodes.new('ShaderNodeMix')
                illum_mix.data_type = 'RGBA'
                illum_mix.location = (tex_x + 300, tex_y)
                
                links.new(illum_tex.outputs['Color'], illum_mix.inputs['Factor'])
                illum_mix.inputs['A'].default_value = (0, 0, 0, 1)
                illum_mix.inputs['B'].default_value = (*emission_color, 1)
                
                links.new(illum_mix.outputs['Result'], emission.inputs['Color'])
                
                tex_y -= 300
        elif props.basetexture:
            # Use base texture alpha as self-illum mask
            # Need to connect base texture alpha to emission strength
            emission.inputs['Color'].default_value = (*emission_color, 1)
            emission.inputs['Strength'].default_value = emission_strength
        else:
            emission.inputs['Color'].default_value = (*emission_color, 1)
            emission.inputs['Strength'].default_value = emission_strength
    else:
        emission.inputs['Strength'].default_value = 0.0
    
    # -------------------------------------------------------------------------
    # RIM LIGHTING (SourceIO-accurate implementation)
    # -------------------------------------------------------------------------
    # Formula: rim = max(saturate(1 - N·V)^exponent × Normal.z, 0) × boost
    # The Normal.z term is Source's ambient cube rim mask (up-facing surfaces)
    # -------------------------------------------------------------------------
    if props.rimlight:
        print(f"[SHADER] Rim light: exponent={props.rimlightexponent}, boost={props.rimlightboost}")
        
        # Geometry node for N·V and Normal.z
        rim_geometry = nodes.new('ShaderNodeNewGeometry')
        rim_geometry.location = (100, -400)
        rim_geometry.label = "Rim Geometry"
        
        # Vector Math: N·V = dot(Normal, Incoming)
        rim_ndotv = nodes.new('ShaderNodeVectorMath')
        rim_ndotv.operation = 'DOT_PRODUCT'
        rim_ndotv.location = (250, -350)
        rim_ndotv.label = "N·V"
        links.new(rim_geometry.outputs['Normal'], rim_ndotv.inputs[0])
        links.new(rim_geometry.outputs['Incoming'], rim_ndotv.inputs[1])
        
        # fresnel = saturate(1 - N·V)
        rim_one_minus = nodes.new('ShaderNodeMath')
        rim_one_minus.operation = 'SUBTRACT'
        rim_one_minus.use_clamp = True  # saturate
        rim_one_minus.location = (400, -350)
        rim_one_minus.inputs[0].default_value = 1.0
        rim_one_minus.label = "1 - N·V (clamped)"
        links.new(rim_ndotv.outputs['Value'], rim_one_minus.inputs[1])
        
        # fresnel^exponent
        rim_power = nodes.new('ShaderNodeMath')
        rim_power.operation = 'POWER'
        rim_power.location = (550, -350)
        rim_power.inputs[1].default_value = props.rimlightexponent
        rim_power.label = "Fresnel^Exp"
        links.new(rim_one_minus.outputs['Value'], rim_power.inputs[0])
        
        # Normal.z = dot(Normal, [0, 0, 1]) - up-facing mask
        rim_normal_z = nodes.new('ShaderNodeVectorMath')
        rim_normal_z.operation = 'DOT_PRODUCT'
        rim_normal_z.location = (250, -500)
        rim_normal_z.inputs[1].default_value = (0.0, 0.0, 1.0)
        rim_normal_z.label = "Normal.z (up mask)"
        links.new(rim_geometry.outputs['Normal'], rim_normal_z.inputs[0])
        
        # fresnel^exp × Normal.z
        rim_mult_z = nodes.new('ShaderNodeMath')
        rim_mult_z.operation = 'MULTIPLY'
        rim_mult_z.location = (700, -400)
        rim_mult_z.label = "Fresnel × Normal.z"
        links.new(rim_power.outputs['Value'], rim_mult_z.inputs[0])
        links.new(rim_normal_z.outputs['Value'], rim_mult_z.inputs[1])
        
        # max(result, 0)
        rim_max = nodes.new('ShaderNodeMath')
        rim_max.operation = 'MAXIMUM'
        rim_max.location = (850, -400)
        rim_max.inputs[1].default_value = 0.0
        rim_max.label = "max(rim, 0)"
        links.new(rim_mult_z.outputs['Value'], rim_max.inputs[0])
        
        # × rimlightboost
        rim_boost = nodes.new('ShaderNodeMath')
        rim_boost.operation = 'MULTIPLY'
        rim_boost.location = (1000, -400)
        rim_boost.inputs[1].default_value = props.rimlightboost
        rim_boost.label = "× Boost"
        links.new(rim_max.outputs['Value'], rim_boost.inputs[0])
        
        # Rim mask from phong exponent texture alpha (if enabled)
        if props.rimmask and phong_tex_node:
            rim_mask_mult = nodes.new('ShaderNodeMath')
            rim_mask_mult.operation = 'MULTIPLY'
            rim_mask_mult.location = (1150, -400)
            rim_mask_mult.label = "× Rim Mask"
            links.new(rim_boost.outputs['Value'], rim_mask_mult.inputs[0])
            # Connect phong exponent texture alpha as rim mask
            links.new(phong_tex_node.outputs['Alpha'], rim_mask_mult.inputs[1])
            rim_final = rim_mask_mult
        else:
            rim_final = rim_boost
        
        # Create rim emission
        rim_emission = nodes.new('ShaderNodeEmission')
        rim_emission.location = (1300, -450)
        rim_emission.inputs['Color'].default_value = (*props.phongtint, 1)
        rim_emission.label = "Rim Emission"
        links.new(rim_final.outputs['Value'], rim_emission.inputs['Strength'])
        
        # Add rim to emission
        add_rim = nodes.new('ShaderNodeAddShader')
        add_rim.location = (1450, -300)
        add_rim.label = "Add Rim"
        links.new(emission.outputs[0], add_rim.inputs[0])
        links.new(rim_emission.outputs[0], add_rim.inputs[1])
        
        emission_output = add_rim.outputs[0]
    else:
        emission_output = emission.outputs[0]
    
    # -------------------------------------------------------------------------
    # LIGHTWARP OVERLAY (SourceIO-style: overlay blend with shading)
    # -------------------------------------------------------------------------
    # Note: In SourceIO, lightwarp is applied as an overlay blend on the final
    # shading result. Since we use Principled BSDF which handles lighting
    # internally, we apply the lightwarp as a color modifier on the base color.
    # This tints the diffuse based on lighting intensity.
    # -------------------------------------------------------------------------
    if lightwarp_color_node and base_tex_node:
        # Create overlay blend: base_color OVERLAY lightwarp_color
        # This tints the base texture based on the lightwarp lookup
        lw_overlay = nodes.new('ShaderNodeMix')
        lw_overlay.data_type = 'RGBA'
        lw_overlay.blend_type = 'OVERLAY'
        lw_overlay.location = (400, 200)
        lw_overlay.inputs['Factor'].default_value = 1.0
        lw_overlay.label = "Lightwarp Overlay"
        
        # Find current base color connection and intercept it
        # The base color should be connected to Principled BSDF
        base_color_links = [l for l in links if l.to_socket == principled.inputs['Base Color']]
        if base_color_links:
            # Get the current source of base color
            base_color_source = base_color_links[0].from_socket
            
            # Remove old connection
            links.remove(base_color_links[0])
            
            # Connect: base_color → overlay.A, lightwarp → overlay.B
            links.new(base_color_source, lw_overlay.inputs['A'])
            links.new(lightwarp_color_node.outputs['Color'], lw_overlay.inputs['B'])
            
            # Connect overlay result to Principled BSDF
            links.new(lw_overlay.outputs['Result'], principled.inputs['Base Color'])
            
            print(f"[SHADER] Lightwarp overlay applied to base color")
        else:
            # No base texture connection, apply directly
            links.new(lightwarp_color_node.outputs['Color'], principled.inputs['Base Color'])
            print(f"[SHADER] Lightwarp applied as base color (no base texture)")
    
    # -------------------------------------------------------------------------
    # COMBINE SHADERS (Diffuse + Envmap + Emission)
    # -------------------------------------------------------------------------
    # Source Engine pipeline:
    #   1. Diffuse lighting (base color * light)
    #   2. + Self-illumination (emission)  
    #   3. + Envmap reflections (additive, ONLY if $envmap specified)
    # -------------------------------------------------------------------------
    
    # Start with diffuse shader output (already connected to add_shader input 0)
    # The emission (self-illum) is already connected to add_shader input 1
    # Current output is add_shader
    current_shader_output = add_shader.outputs['Shader']
    
    # ADD envmap if present (Source Engine envmap is ADDITIVE)
    if envmap_enabled and envmap_factor_output:
        # Check if we have an envmap image or should use world
        use_world_env = (envmap_image is None)
        
        if use_world_env:
            # Check if world has an environment texture
            world = bpy.context.scene.world
            has_world_env = False
            try:
                has_world_env = (world and world.use_nodes and 
                               any(n.type == 'TEX_ENVIRONMENT' for n in world.node_tree.nodes))
            except:
                pass
            
            if not has_world_env:
                print(f"[ENVMAP] WARNING: No envmap texture loaded and no world environment.")
                print(f"[ENVMAP] Skipping envmap to avoid purple color.")
                print(f"[ENVMAP] To fix: Either convert the VTF cubemap or add an HDRI to World settings.")
                envmap_enabled = False
        
        if envmap_enabled:
            # Get reflection vector using Texture Coordinate node
            tex_coord = nodes.new('ShaderNodeTexCoord')
            tex_coord.location = (100, -600)
            tex_coord.label = "Envmap Coords"
            
            # Environment texture node
            env_texture = nodes.new('ShaderNodeTexEnvironment')
            env_texture.location = (300, -600)
            
            if envmap_image:
                env_texture.image = envmap_image
                env_texture.label = f"Envmap: {envmap_image.name}"
                print(f"[ENVMAP] Using loaded envmap: {envmap_image.name}")
            else:
                env_texture.label = "World Environment"
                print(f"[ENVMAP] Using world environment")
            
            links.new(tex_coord.outputs['Reflection'], env_texture.inputs['Vector'])
            
            # Multiply sampled color by envmaptint
            tint_mult = nodes.new('ShaderNodeMix')
            tint_mult.data_type = 'RGBA'
            tint_mult.blend_type = 'MULTIPLY'
            tint_mult.location = (500, -600)
            tint_mult.inputs['Factor'].default_value = 1.0
            tint_mult.inputs['B'].default_value = (*props.envmaptint, 1.0)
            tint_mult.label = "Envmap Tint"
            links.new(env_texture.outputs['Color'], tint_mult.inputs['A'])
            
            # Scale by the envmap factor (mask, fresnel, contrast)
            strength_mult = nodes.new('ShaderNodeMix')
            strength_mult.data_type = 'RGBA'
            strength_mult.location = (700, -600)
            strength_mult.inputs['A'].default_value = (0, 0, 0, 1)
            strength_mult.label = "Envmap Strength"
            links.new(envmap_factor_output, strength_mult.inputs['Factor'])
            links.new(tint_mult.outputs['Result'], strength_mult.inputs['B'])
            
            # Create emission shader for envmap (truly additive)
            envmap_emission = nodes.new('ShaderNodeEmission')
            envmap_emission.location = (900, -600)
            envmap_emission.inputs['Strength'].default_value = 1.0
            envmap_emission.label = "Envmap Emission"
            links.new(strength_mult.outputs['Result'], envmap_emission.inputs['Color'])
            
            # Add the envmap emission to the current shader
            envmap_add = nodes.new('ShaderNodeAddShader')
            envmap_add.location = (1100, -300)
            envmap_add.label = "Add Envmap"
            
            links.new(current_shader_output, envmap_add.inputs[0])
            links.new(envmap_emission.outputs['Emission'], envmap_add.inputs[1])
            
            current_shader_output = envmap_add.outputs['Shader']
    
    # Update add_shader connections (diffuse + emission already connected above)
    # The emission_output was set up in the rim lighting / self-illum section
    links.new(emission_output, add_shader.inputs[1])
    
    # -------------------------------------------------------------------------
    # DETAIL TEXTURE
    # -------------------------------------------------------------------------
    if props.detail:
        img = load_texture(props.detail, 'sRGB')
        if img:
            detail_tex = nodes.new('ShaderNodeTexImage')
            detail_tex.location = (tex_x - 200, tex_y)
            detail_tex.image = img
            detail_tex.label = "Detail Texture"
            
            # Detail UV scaling
            detail_uv = nodes.new('ShaderNodeUVMap')
            detail_uv.location = (tex_x - 600, tex_y)
            
            detail_mapping = nodes.new('ShaderNodeMapping')
            detail_mapping.location = (tex_x - 400, tex_y)
            detail_mapping.inputs['Scale'].default_value = (
                props.detailscale, props.detailscale, 1.0
            )
            
            links.new(detail_uv.outputs['UV'], detail_mapping.inputs['Vector'])
            links.new(detail_mapping.outputs['Vector'], detail_tex.inputs['Vector'])
            
            # Detail blending - need to insert into the base color chain
            # For simplicity, we'll use overlay mix (TODO: proper detail modes)
            
            tex_y -= 300
    
    # -------------------------------------------------------------------------
    # TRANSPARENCY
    # -------------------------------------------------------------------------
    if props.translucent or props.alphatest:
        # For alphatest materials
        if props.alphatest and props.basetexture and base_tex_node:
            # Check if the base texture actually has alpha data
            has_alpha = False
            if base_tex_node.image:
                img = base_tex_node.image
                print(f"[VLG DEBUG] Base texture: {img.name}")
                print(f"[VLG DEBUG] Channels: {img.channels}, Depth: {img.depth}")
                print(f"[VLG DEBUG] Alpha mode: {img.alpha_mode}")
                has_alpha = img.channels == 4
                
                if not has_alpha:
                    print(f"[VLG WARNING] Base texture has no alpha channel ({img.channels} channels)")
            
            # Check if $allowalphatocoverage is enabled (softer edges)
            if props.allowalphatocoverage:
                # Use HASHED blend mode for soft dithered edges (similar to alpha-to-coverage)
                print(f"[VLG DEBUG] Using HASHED mode for $allowalphatocoverage (soft edges)")
                if hasattr(material, 'blend_method'):
                    material.blend_method = 'HASHED'
                if hasattr(material, 'shadow_method'):
                    material.shadow_method = 'HASHED'
                
                # Connect alpha directly - HASHED mode handles soft dithering
                links.new(base_tex_node.outputs['Alpha'], principled.inputs['Alpha'])
                links.new(current_shader_output, output.inputs['Surface'])
            else:
                # Hard cutoff alphatest - use Mix Shader approach
                print(f"[VLG DEBUG] Using hard cutoff alphatest (threshold: {props.alphatestreference})")
                if hasattr(material, 'blend_method'):
                    material.blend_method = 'BLEND'
                if hasattr(material, 'shadow_method'):
                    material.shadow_method = 'CLIP'
                
                # Create alpha test comparison node
                alpha_test = nodes.new('ShaderNodeMath')
                alpha_test.operation = 'GREATER_THAN'
                alpha_test.location = (output.location[0] - 600, output.location[1] - 200)
                alpha_test.inputs[1].default_value = props.alphatestreference
                alpha_test.label = "Alpha Test"
                
                # Create Transparent BSDF
                transparent = nodes.new('ShaderNodeBsdfTransparent')
                transparent.location = (output.location[0] - 400, output.location[1] - 150)
                transparent.label = "Transparent"
                
                # Create Mix Shader
                mix_shader = nodes.new('ShaderNodeMixShader')
                mix_shader.location = (output.location[0] - 200, output.location[1])
                mix_shader.label = "Alpha Cutoff"
                
                # Connect: Alpha -> Greater Than -> Mix Factor
                links.new(base_tex_node.outputs['Alpha'], alpha_test.inputs[0])
                links.new(alpha_test.outputs['Value'], mix_shader.inputs['Fac'])
                links.new(transparent.outputs['BSDF'], mix_shader.inputs[1])
                links.new(current_shader_output, mix_shader.inputs[2])
                links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])
        
        elif props.translucent:
            # For translucent materials
            if hasattr(material, 'blend_method'):
                material.blend_method = 'BLEND'
            if hasattr(material, 'shadow_method'):
                material.shadow_method = 'HASHED'
            if hasattr(material, 'surface_render_method'):
                material.surface_render_method = 'BLENDED'
            
            # Connect alpha with cleanup for halo artifacts
            if props.basetexture and base_tex_node:
                # Step 1: Create hard cutoff mask (alpha > 0.1 ? 1 : 0)
                math_gt = nodes.new('ShaderNodeMath')
                math_gt.location = (base_tex_node.location[0] + 250, base_tex_node.location[1] - 150)
                math_gt.operation = 'GREATER_THAN'
                math_gt.inputs[1].default_value = 0.1  # Hard cutoff threshold
                math_gt.label = "Alpha Cutoff"
                
                # Step 2: Multiply original alpha by mask to zero out low values
                math_mul = nodes.new('ShaderNodeMath')
                math_mul.location = (base_tex_node.location[0] + 450, base_tex_node.location[1] - 150)
                math_mul.operation = 'MULTIPLY'
                math_mul.use_clamp = True
                math_mul.label = "Clean Alpha"
                
                links.new(base_tex_node.outputs['Alpha'], math_gt.inputs[0])
                links.new(base_tex_node.outputs['Alpha'], math_mul.inputs[0])
                links.new(math_gt.outputs['Value'], math_mul.inputs[1])
                links.new(math_mul.outputs['Value'], principled.inputs['Alpha'])
            else:
                principled.inputs['Alpha'].default_value = props.alpha
            
            links.new(current_shader_output, output.inputs['Surface'])
        
        else:
            # Fallback
            if hasattr(material, 'blend_method'):
                material.blend_method = 'BLEND'
            if props.basetexture and base_tex_node:
                links.new(base_tex_node.outputs['Alpha'], principled.inputs['Alpha'])
            links.new(current_shader_output, output.inputs['Surface'])
    else:
        if hasattr(material, 'blend_method'):
            material.blend_method = 'OPAQUE'
        links.new(current_shader_output, output.inputs['Surface'])
    
    # -------------------------------------------------------------------------
    # BACKFACE CULLING AND TRANSPARENCY
    # -------------------------------------------------------------------------
    material.use_backface_culling = not props.nocull
    
    # For double-sided transparent materials, ensure backfaces render correctly
    if props.nocull and (props.translucent or props.alphatest):
        if hasattr(material, 'show_transparent_back'):
            material.show_transparent_back = True
    
    # -------------------------------------------------------------------------
    # ARRANGE NODES FOR CLEAN LAYOUT
    # -------------------------------------------------------------------------
    arrange_nodes(nodes, output)


def arrange_nodes(nodes, output_node):
    """Arrange shader nodes in a clean, organized layout.
    
    Organizes nodes from right to left based on their connection depth
    from the output node, with consistent spacing.
    """
    NODE_WIDTH = 250
    NODE_HEIGHT = 200
    COLUMN_SPACING = 300
    ROW_SPACING = 250
    
    # Calculate depth of each node (distance from output)
    depths = {}
    
    def get_depth(node, current_depth=0):
        if node.name in depths:
            # Take the maximum depth if visited from multiple paths
            depths[node.name] = max(depths[node.name], current_depth)
            return
        depths[node.name] = current_depth
        
        # Traverse inputs
        for input_socket in node.inputs:
            for link in input_socket.links:
                get_depth(link.from_node, current_depth + 1)
    
    # Start from output
    get_depth(output_node, 0)
    
    # Group nodes by depth
    columns = {}
    for node_name, depth in depths.items():
        if depth not in columns:
            columns[depth] = []
        columns[depth].append(node_name)
    
    # Position nodes
    max_depth = max(depths.values()) if depths else 0
    
    for depth, node_names in columns.items():
        # X position: output on right, inputs on left
        x = (max_depth - depth) * -COLUMN_SPACING
        
        # Sort nodes in column by type for consistency
        def sort_key(name):
            node = nodes.get(name)
            if not node:
                return (999, name)
            type_order = {
                'OUTPUT_MATERIAL': 0,
                'BSDF_PRINCIPLED': 1,
                'MIX_SHADER': 2,
                'ADD_SHADER': 3,
                'EMISSION': 4,
                'TEX_IMAGE': 10,
                'NORMAL_MAP': 11,
                'VECT_MATH': 20,
                'MATH': 21,
                'MIX': 22,
                'CLAMP': 23,
                'NEW_GEOMETRY': 30,
                'FRESNEL': 31,
            }
            return (type_order.get(node.type, 50), name)
        
        node_names.sort(key=sort_key)
        
        # Y position: stack vertically, centered
        total_height = len(node_names) * ROW_SPACING
        start_y = total_height / 2
        
        for i, node_name in enumerate(node_names):
            node = nodes.get(node_name)
            if node:
                node.location.x = x
                node.location.y = start_y - (i * ROW_SPACING)
    
    # Handle any unconnected nodes (textures at the left)
    unconnected = [n for n in nodes if n.name not in depths]
    if unconnected:
        x = (max_depth + 1) * -COLUMN_SPACING
        for i, node in enumerate(unconnected):
            node.location.x = x
            node.location.y = 400 - (i * ROW_SPACING)


# ============================================================================
# OPERATORS
# ============================================================================

class VLG_OT_ApplyShader(Operator):
    """Apply VertexLitGeneric shader to the active material"""
    bl_idname = "vlg.apply_shader"
    bl_label = "Apply VertexLitGeneric"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material
    
    def execute(self, context):
        mat = context.active_object.active_material
        props = mat.vlg_props
        apply_vlg_material(mat, props)
        self.report({'INFO'}, f"Applied VertexLitGeneric shader to {mat.name}")
        return {'FINISHED'}


class VLG_OT_CreateMaterial(Operator):
    """Create a new material with VertexLitGeneric shader"""
    bl_idname = "vlg.create_material"
    bl_label = "Create VertexLitGeneric Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def execute(self, context):
        obj = context.active_object
        
        # Create new material
        mat = bpy.data.materials.new(name="VertexLitGeneric")
        mat.use_nodes = True
        
        # Assign to object
        if obj.data.materials:
            obj.data.materials.append(mat)
        else:
            obj.data.materials.append(mat)
        
        obj.active_material = mat
        
        # Apply default VLG shader
        props = mat.vlg_props
        apply_vlg_material(mat, props)
        
        self.report({'INFO'}, f"Created VertexLitGeneric material: {mat.name}")
        return {'FINISHED'}


class VLG_OT_ImportVMT(Operator):
    """Import a Source Engine VMT file and create a new material"""
    bl_idname = "vlg.import_vmt"
    bl_label = "Import VMT"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.vmt", options={'HIDDEN'})
    
    def execute(self, context):
        try:
            # Read VMT file
            with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Get material name from filename
            vmt_name = os.path.splitext(os.path.basename(self.filepath))[0]
            
            # Create new material
            mat = bpy.data.materials.new(name=f"VLG_{vmt_name}")
            mat.use_nodes = True
            
            print(f"\n[VLG] Created new material: {mat.name}")
            print(f"[VLG] Importing from: {self.filepath}")
            
            # Store VMT path for refresh functionality
            mat['vlg_vmt_path'] = self.filepath
            
            # Parse VMT into material properties
            props = mat.vlg_props
            parse_vmt(content, props, os.path.dirname(self.filepath))
            
            # Apply the shader
            apply_vlg_material(mat, props)
            mat['vlg_loaded'] = True
            
            # Assign to active object if there is one
            if context.active_object and hasattr(context.active_object, 'data') and hasattr(context.active_object.data, 'materials'):
                obj = context.active_object
                # Add material slot if needed
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(mat)
                else:
                    # Add as new slot
                    obj.data.materials.append(mat)
                obj.active_material = mat
                print(f"[VLG] Assigned material to: {obj.name}")
            
            self.report({'INFO'}, f"Created material '{mat.name}' from VMT")
            print(f"[VLG] Import complete!\n")
            
        except Exception as e:
            import traceback
            print(f"[VLG ERROR] {str(e)}")
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Failed to import VMT: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class VLG_OT_ExportVMT(Operator):
    """Export material settings as Source Engine VMT file"""
    bl_idname = "vlg.export_vmt"
    bl_label = "Export VMT"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.vmt", options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material
    
    def execute(self, context):
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        try:
            vmt_content = generate_vmt(props, mat.name)
            
            with open(self.filepath, 'w') as f:
                f.write(vmt_content)
            
            self.report({'INFO'}, f"Exported VMT: {os.path.basename(self.filepath)}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export VMT: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.filepath = context.active_object.active_material.name + ".vmt"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class VLG_OT_RefreshMaterials(Operator):
    """Rebuild VLG shader for all selected objects using current Blender properties"""
    bl_idname = "vlg.refresh_materials"
    bl_label = "Rebuild Shader"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects and len(context.selected_objects) > 0
    
    def execute(self, context):
        refreshed_count = 0
        skipped_count = 0
        error_count = 0
        
        # Collect all unique materials from selected objects
        materials_to_refresh = set()
        for obj in context.selected_objects:
            if hasattr(obj, 'data') and hasattr(obj.data, 'materials'):
                for mat in obj.data.materials:
                    if mat is not None:
                        materials_to_refresh.add(mat)
        
        if not materials_to_refresh:
            self.report({'WARNING'}, "No materials found on selected objects")
            return {'CANCELLED'}
        
        for mat in materials_to_refresh:
            # Check if this is a VLG material
            if mat.get('vlg_loaded', False) or hasattr(mat, 'vlg_props'):
                try:
                    props = mat.vlg_props
                    apply_vlg_material(mat, props)
                    mat['vlg_loaded'] = True
                    print(f"[VLG] Rebuilt shader: {mat.name}")
                    refreshed_count += 1
                except Exception as e:
                    print(f"[VLG] Error rebuilding {mat.name}: {e}")
                    error_count += 1
            else:
                skipped_count += 1
        
        msg = f"Rebuilt {refreshed_count} material(s)"
        if skipped_count > 0:
            msg += f", skipped {skipped_count} (not VLG)"
        if error_count > 0:
            msg += f", {error_count} error(s)"
        
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class VLG_OT_ReloadVMT(Operator):
    """Reload VMT files from disk for all selected objects"""
    bl_idname = "vlg.reload_vmt"
    bl_label = "Reload VMT"
    bl_options = {'REGISTER', 'UNDO'}
    
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default="*.vmt", options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects and len(context.selected_objects) > 0
    
    def find_vmt_file(self, mat, base_directory):
        """Try multiple strategies to find the VMT file for a material"""
        stored_path = mat.get('vlg_vmt_path', '')
        mat_name = mat.name.replace("VLG_", "")  # Remove VLG_ prefix if present
        
        # Strategy 1: Stored path exists directly on disk
        if stored_path and os.path.exists(stored_path):
            print(f"[VLG] Found via stored path: {stored_path}")
            return stored_path
        
        # Strategy 2: Stored path is relative (like materials/models/...) - try with base directory
        if stored_path and base_directory:
            # Try combining base directory with stored relative path
            # e.g., base="D:/SteamLibrary/.../garrysmod" + stored="materials/models/ouch/mat.vmt"
            combined = os.path.join(base_directory, stored_path)
            if os.path.exists(combined):
                print(f"[VLG] Found via combined path: {combined}")
                return combined
            
            # Also try with just the filename from stored path
            stored_filename = os.path.basename(stored_path)
            # Search recursively
            for root, dirs, files in os.walk(base_directory):
                if stored_filename in files:
                    found_path = os.path.join(root, stored_filename)
                    print(f"[VLG] Found via recursive search: {found_path}")
                    return found_path
        
        # Strategy 3: Search by material name in base directory
        if base_directory:
            # Direct path
            direct_path = os.path.join(base_directory, mat_name + ".vmt")
            if os.path.exists(direct_path):
                print(f"[VLG] Found via direct name: {direct_path}")
                return direct_path
            
            # Recursive search by material name
            for root, dirs, files in os.walk(base_directory):
                vmt_name = mat_name + ".vmt"
                if vmt_name in files:
                    found_path = os.path.join(root, vmt_name)
                    print(f"[VLG] Found via recursive name search: {found_path}")
                    return found_path
        
        return None
    
    def execute(self, context):
        reloaded_count = 0
        not_found_count = 0
        error_count = 0
        
        # Collect all unique materials from selected objects
        materials_to_reload = set()
        for obj in context.selected_objects:
            if hasattr(obj, 'data') and hasattr(obj.data, 'materials'):
                for mat in obj.data.materials:
                    if mat is not None:
                        materials_to_reload.add(mat)
        
        if not materials_to_reload:
            self.report({'WARNING'}, "No materials found on selected objects")
            return {'CANCELLED'}
        
        for mat in materials_to_reload:
            # Try to find VMT file using multiple strategies
            vmt_path = self.find_vmt_file(mat, self.directory)
            
            if vmt_path:
                try:
                    # Re-read the VMT file
                    with open(vmt_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    print(f"[VLG] Reloading VMT for {mat.name} from: {vmt_path}")
                    
                    # Get material properties
                    props = mat.vlg_props
                    
                    # Clear texture paths so they get reloaded
                    props.basetexture = ""
                    props.bumpmap = ""
                    props.phongexponenttexture = ""
                    props.envmapmask = ""
                    props.selfillummask = ""
                    props.lightwarptexture = ""
                    props.detail = ""
                    
                    # Re-parse VMT
                    parse_vmt(content, props, os.path.dirname(vmt_path))
                    
                    # Update stored path to the actual disk path
                    mat['vlg_vmt_path'] = vmt_path
                    
                    # Re-apply shader
                    apply_vlg_material(mat, props)
                    mat['vlg_loaded'] = True
                    
                    print(f"[VLG] Reloaded material: {mat.name}")
                    reloaded_count += 1
                    
                except Exception as e:
                    print(f"[VLG] Error reloading {mat.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    error_count += 1
            else:
                clean_name = mat.name.replace("VLG_", "")
                stored = mat.get('vlg_vmt_path', 'none')
                print(f"[VLG] VMT not found for: {mat.name}")
                print(f"       Looking for: {clean_name}.vmt")
                print(f"       Stored path: {stored}")
                print(f"       Search dir: {self.directory}")
                not_found_count += 1
        
        msg = f"Reloaded {reloaded_count} material(s)"
        if not_found_count > 0:
            msg += f", {not_found_count} VMT(s) not found - check console"
        if error_count > 0:
            msg += f", {error_count} error(s)"
        
        self.report({'INFO'} if reloaded_count > 0 else {'WARNING'}, msg)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Collect material info
        mat_info = []  # List of (material, name, stored_path)
        
        for obj in context.selected_objects:
            if hasattr(obj, 'data') and hasattr(obj.data, 'materials'):
                for mat in obj.data.materials:
                    if mat:
                        stored_path = mat.get('vlg_vmt_path', '')
                        mat_info.append((mat, mat.name, stored_path))
        
        if not mat_info:
            self.report({'WARNING'}, "No materials found on selected objects")
            return {'CANCELLED'}
        
        # Strategy 1: Check if any stored path exists directly
        for mat, name, stored_path in mat_info:
            if stored_path and os.path.exists(stored_path):
                self.directory = os.path.dirname(stored_path)
                print(f"[VLG] Found existing path: {stored_path}")
                return self.execute(context)
        
        # Strategy 2: Try common Steam library locations with stored relative paths
        common_bases = [
            "D:/SteamLibrary/steamapps/common/GarrysMod/garrysmod",
            "E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod",
            "F:/SteamLibrary/steamapps/common/GarrysMod/garrysmod",
            "C:/Program Files (x86)/Steam/steamapps/common/GarrysMod/garrysmod",
            "C:/Program Files/Steam/steamapps/common/GarrysMod/garrysmod",
            "C:/Steam/steamapps/common/GarrysMod/garrysmod",
        ]
        
        for mat, name, stored_path in mat_info:
            if stored_path:
                for base in common_bases:
                    if os.path.exists(base):
                        test_path = os.path.join(base, stored_path)
                        if os.path.exists(test_path):
                            # Found it! Update the stored path to the full path
                            mat['vlg_vmt_path'] = test_path
                            self.directory = os.path.dirname(test_path)
                            print(f"[VLG] Auto-resolved path: {test_path}")
                            return self.execute(context)
        
        # Strategy 3: Search for VMT files by name in common locations
        for mat, name, stored_path in mat_info:
            clean_name = name.replace("VLG_", "") + ".vmt"
            for base in common_bases:
                if os.path.exists(base):
                    materials_dir = os.path.join(base, "materials")
                    if os.path.exists(materials_dir):
                        # Search recursively (limit depth to avoid long searches)
                        for root, dirs, files in os.walk(materials_dir):
                            # Limit search depth
                            depth = root.replace(materials_dir, '').count(os.sep)
                            if depth > 6:
                                dirs[:] = []  # Don't go deeper
                                continue
                            if clean_name in files:
                                found_path = os.path.join(root, clean_name)
                                mat['vlg_vmt_path'] = found_path
                                self.directory = root
                                print(f"[VLG] Found via search: {found_path}")
                                return self.execute(context)
        
        # Strategy 4: Check addons folder
        for mat, name, stored_path in mat_info:
            clean_name = name.replace("VLG_", "") + ".vmt"
            for base in common_bases:
                addons_dir = os.path.join(base, "addons")
                if os.path.exists(addons_dir):
                    for root, dirs, files in os.walk(addons_dir):
                        depth = root.replace(addons_dir, '').count(os.sep)
                        if depth > 6:
                            dirs[:] = []
                            continue
                        if clean_name in files:
                            found_path = os.path.join(root, clean_name)
                            mat['vlg_vmt_path'] = found_path
                            self.directory = root
                            print(f"[VLG] Found in addons: {found_path}")
                            return self.execute(context)
        
        # Nothing found - print debug info and show browser as last resort
        print("\n" + "="*60)
        print("[VLG] RELOAD VMT - Could not auto-find VMT files")
        print("Looking for:")
        for mat, name, stored_path in mat_info[:5]:
            clean_name = name.replace("VLG_", "")
            print(f"  - {clean_name}.vmt (stored: {stored_path or 'none'})")
        print("\nSearched in:")
        for base in common_bases:
            status = "EXISTS" if os.path.exists(base) else "NOT FOUND"
            print(f"  - {base} [{status}]")
        print("="*60 + "\n")
        
        self.report({'WARNING'}, "Could not auto-find VMT files - please browse to folder")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# ============================================================================
# VMT PARSING
# ============================================================================

def parse_vmt(content, props, base_path=""):
    """Parse VMT content and set material properties"""
    
    print("\n" + "="*60)
    print("VMT PARSER DEBUG OUTPUT")
    print("="*60)
    
    # Remove comments (// style)
    content_no_comments = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    
    # Multiple patterns to catch different VMT formats:
    # Pattern 1: "$key" "value" (both quoted)
    # Pattern 2: "$key" "[vector]" (key quoted, vector in brackets)  
    # Pattern 3: $key "value" (key unquoted)
    # Pattern 4: "$key" value (value unquoted)
    
    parsed_values = {}
    
    # Pattern for: "$key" "value" or "$key" "[1 2 3]"
    # Note: \s* allows zero or more whitespace (some VMTs have no space like "$key""value")
    pattern1 = r'"\$(\w+)"\s*"([^"]*)"'
    for match in re.finditer(pattern1, content_no_comments, re.IGNORECASE):
        key = match.group(1).lower()
        value = match.group(2)
        parsed_values[key] = value
        print(f"  [PARSED] ${key} = \"{value}\"")
    
    # Pattern for: "$key" "[1 2 3]" (vector in separate brackets)
    pattern2 = r'"\$(\w+)"\s*"\[([^\]]*)\]"'
    for match in re.finditer(pattern2, content_no_comments, re.IGNORECASE):
        key = match.group(1).lower()
        value = match.group(2)
        if key not in parsed_values:  # Don't overwrite
            parsed_values[key] = value
            print(f"  [PARSED] ${key} = \"[{value}]\"")
    
    # Pattern for unquoted key, quoted value: $key "value"
    pattern3 = r'(?<!")\$(\w+)\s+"([^"]*)"'
    for match in re.finditer(pattern3, content_no_comments, re.IGNORECASE):
        key = match.group(1).lower()
        value = match.group(2)
        if key not in parsed_values:
            parsed_values[key] = value
            print(f"  [PARSED] ${key} = \"{value}\"")
    
    # Pattern for completely unquoted: $key value (number or simple word)
    # This catches: $alphatest 1, $phong 1, $nocull 1, etc.
    pattern4 = r'(?<!")\$(\w+)\s+([0-9.]+|true|false|yes|no)\b'
    for match in re.finditer(pattern4, content_no_comments, re.IGNORECASE):
        key = match.group(1).lower()
        value = match.group(2)
        if key not in parsed_values:
            parsed_values[key] = value
            print(f"  [PARSED] ${key} = {value} (unquoted)")
    
    # Pattern for unquoted key with bracketed vector: $key [1 2 3]
    pattern5 = r'(?<!")\$(\w+)\s+\[([^\]]*)\]'
    for match in re.finditer(pattern5, content_no_comments, re.IGNORECASE):
        key = match.group(1).lower()
        value = match.group(2)
        if key not in parsed_values:
            parsed_values[key] = value
            print(f"  [PARSED] ${key} = [{value}] (unquoted)")
    
    print(f"\nTotal parsed: {len(parsed_values)} parameters")
    print("="*60 + "\n")
    
    # Now apply all parsed values to properties
    for key, value in parsed_values.items():
        if not value:
            continue
        
        # Map VMT keys to properties
        if key == 'basetexture':
            props.basetexture = resolve_texture_path(value, base_path)
        elif key == 'bumpmap':
            props.bumpmap = resolve_texture_path(value, base_path)
        elif key == 'color' or key == 'color2':
            color = parse_color(value)
            if key == 'color':
                props.color = color
            else:
                props.color2 = color
        elif key == 'alpha':
            props.alpha = safe_float(value, 1.0)
        elif key == 'phong':
            props.phong = value.lower() in ('1', 'true', 'yes')
        elif key == 'phongexponent':
            props.phongexponent = safe_float(value, 20.0)
        elif key == 'phongboost':
            props.phongboost = safe_float(value, 1.0)
        elif key == 'phongfresnelranges':
            props.phongfresnelranges = parse_vector3(value)
        elif key == 'phongtint':
            props.phongtint = parse_color(value)
        elif key == 'phongalbedotint':
            props.phongalbedotint = value.lower() in ('1', 'true', 'yes')
        elif key == 'phongalbedoboost':
            props.phongalbedoboost = safe_float(value, 1.0)
        elif key == 'phongexponenttexture':
            props.phongexponenttexture = resolve_texture_path(value, base_path)
        elif key == 'basemapalphaphongmask':
            props.basemapalphaphongmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'invertphongmask':
            props.invertphongmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'phongdisablehalflambert':
            props.phongdisablehalflambert = value.lower() in ('1', 'true', 'yes')
        elif key == 'lightwarptexture':
            props.lightwarptexture = resolve_texture_path(value, base_path)
            print(f"[VMT] Found lightwarptexture: {props.lightwarptexture}")
            print(f"[VMT] NOTE: Lightwarptexture affects diffuse shading but is not fully implemented in Blender yet")
        elif key == 'phongwarptexture':
            props.phongwarptexture = resolve_texture_path(value, base_path)
        elif key == 'envmap':
            # Special values like 'env_cubemap' shouldn't be resolved as file paths
            if value.lower() in ('env_cubemap', 'environment maps/metal_generic_001'):
                props.envmap = value
            else:
                props.envmap = resolve_texture_path(value, base_path)
        elif key == 'envmaptint':
            props.envmaptint = parse_color(value)
        elif key == 'envmapcontrast':
            props.envmapcontrast = safe_float(value, 0.0)
        elif key == 'envmapsaturation':
            props.envmapsaturation = safe_float(value, 1.0)
        elif key == 'envmapfresnel':
            props.envmapfresnel = safe_float(value, 0.0)
        elif key == 'envmapmask':
            props.envmapmask = resolve_texture_path(value, base_path)
        elif key == 'basealphaenvmapmask':
            props.basealphaenvmapmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'normalmapalphaenvmapmask':
            props.normalmapalphaenvmapmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'selfillum':
            props.selfillum = value.lower() in ('1', 'true', 'yes')
        elif key == 'selfillumtint':
            props.selfillumtint = parse_color(value)
        elif key == 'selfillummask':
            props.selfillummask = resolve_texture_path(value, base_path)
        elif key == 'rimlight':
            props.rimlight = value.lower() in ('1', 'true', 'yes')
        elif key == 'rimlightexponent':
            props.rimlightexponent = safe_float(value, 4.0)
        elif key == 'rimlightboost':
            props.rimlightboost = safe_float(value, 1.0)
        elif key == 'rimmask':
            props.rimmask = value.lower() in ('1', 'true', 'yes')
        elif key == 'detail':
            props.detail = resolve_texture_path(value, base_path)
        elif key == 'detailscale':
            props.detailscale = safe_float(value, 4.0)
        elif key == 'detailblendfactor':
            props.detailblendfactor = safe_float(value, 1.0)
        elif key == 'detailblendmode':
            props.detailblendmode = value
        elif key == 'translucent':
            props.translucent = value.lower() in ('1', 'true', 'yes')
        elif key == 'alphatest':
            props.alphatest = value.lower() in ('1', 'true', 'yes')
        elif key == 'alphatestreference':
            props.alphatestreference = safe_float(value, 0.5)
        elif key == 'allowalphatocoverage':
            props.allowalphatocoverage = value.lower() in ('1', 'true', 'yes')
        elif key == 'additive':
            props.additive = value.lower() in ('1', 'true', 'yes')
        elif key == 'halflambert':
            props.halflambert = value.lower() in ('1', 'true', 'yes')
        elif key == 'nocull':
            props.nocull = value.lower() in ('1', 'true', 'yes')
        elif key == 'model':
            props.model = value.lower() in ('1', 'true', 'yes')
        elif key == 'blendtintbybasealpha':
            props.blendtintbybasealpha = value.lower() in ('1', 'true', 'yes')


def resolve_texture_path(vmt_path, base_path):
    """Convert VMT texture path to actual file path. Supports VTF files directly."""
    # Remove quotes and normalize slashes
    vmt_path = vmt_path.strip('"\'').replace('\\', '/').replace('//', '/')
    
    # Extensions to try - prioritize pre-converted formats (TGA, PNG) over VTF
    # This allows users to use pre-converted textures for faster loading
    extensions = ['.tga', '.png', '.jpg', '.jpeg', '.dds', '.bmp', '.vtf', '']
    
    # Get just the filename without path for local search
    texture_filename = os.path.basename(vmt_path)
    
    print(f"  [TEXTURE] Looking for: {vmt_path}")
    
    # Strategy 1: Check same directory as VMT file
    for ext in extensions:
        full_path = os.path.join(base_path, texture_filename + ext)
        if os.path.exists(full_path):
            print(f"  [TEXTURE] FOUND (local): {full_path}")
            return full_path
    
    # Strategy 2: Find 'materials' folder and resolve from there
    # VMT paths are relative to the 'materials' folder
    base_path_lower = base_path.lower().replace('\\', '/')
    if 'materials' in base_path_lower:
        # Find the materials root
        idx = base_path_lower.find('materials')
        materials_root = base_path[:idx + len('materials')]
        
        for ext in extensions:
            full_path = os.path.join(materials_root, vmt_path.replace('/', os.sep) + ext)
            if os.path.exists(full_path):
                print(f"  [TEXTURE] FOUND (materials): {full_path}")
                return full_path
    
    # Strategy 3: Try relative to base path with full VMT path
    for ext in extensions:
        full_path = os.path.join(base_path, vmt_path.replace('/', os.sep) + ext)
        if os.path.exists(full_path):
            print(f"  [TEXTURE] FOUND (relative): {full_path}")
            return full_path
    
    # Strategy 4: Check parent directories for materials folder
    current = base_path
    for _ in range(10):  # Go up max 10 levels
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
        
        materials_path = os.path.join(current, 'materials', vmt_path.replace('/', os.sep))
        for ext in extensions:
            full_path = materials_path + ext
            if os.path.exists(full_path):
                print(f"  [TEXTURE] FOUND (parent): {full_path}")
                return full_path
    
    print(f"  [TEXTURE] NOT FOUND: {vmt_path}")
    print(f"           Searched in: {base_path}")
    
    return vmt_path  # Return as-is if not found


def safe_float(value, default=0.0):
    """Safely convert a string to float, handling edge cases"""
    if value is None:
        return default
    
    # Clean up the value
    value = str(value).strip()
    
    # Handle empty strings
    if not value:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_color(value):
    """Parse color from VMT format like '[0.392 0.392 0.38]' or '0.5 0.5 0.5'"""
    if not value:
        return (1.0, 1.0, 1.0)
    
    # Remove brackets, braces, quotes
    value = value.strip('[]{}"\' ')
    
    # Replace commas with spaces and split, filtering out empty strings
    parts = [p.strip() for p in value.replace(',', ' ').split() if p.strip()]
    
    if len(parts) >= 3:
        try:
            r = safe_float(parts[0], 1.0)
            g = safe_float(parts[1], 1.0)
            b = safe_float(parts[2], 1.0)
            
            # VMT colors can be in 0-255 or 0-1 range
            if r > 1.0 or g > 1.0 or b > 1.0:
                r /= 255.0
                g /= 255.0
                b /= 255.0
            
            return (max(0.0, min(2.0, r)), max(0.0, min(2.0, g)), max(0.0, min(2.0, b)))
        except:
            pass
    
    return (1.0, 1.0, 1.0)


def parse_vector3(value):
    """Parse 3-component vector from VMT format like '[1 0.1 0]'"""
    if not value:
        return (0.0, 0.5, 1.0)
    
    # Remove brackets, braces, quotes
    value = value.strip('[]{}"\' ')
    
    # Replace commas with spaces and split, filtering out empty strings
    parts = [p.strip() for p in value.replace(',', ' ').split() if p.strip()]
    
    if len(parts) >= 3:
        return (
            safe_float(parts[0], 0.0),
            safe_float(parts[1], 0.5),
            safe_float(parts[2], 1.0)
        )
    
    return (0.0, 0.5, 1.0)


def generate_vmt(props, material_name):
    """Generate VMT file content from properties"""
    lines = ['"VertexLitGeneric"', '{']
    
    def add_param(key, value, condition=True):
        if condition:
            if isinstance(value, bool):
                lines.append(f'\t"${key}" "{1 if value else 0}"')
            elif isinstance(value, (int, float)):
                lines.append(f'\t"${key}" "{value}"')
            elif isinstance(value, tuple):
                if len(value) == 3:
                    lines.append(f'\t"${key}" "[{value[0]:.3f} {value[1]:.3f} {value[2]:.3f}]"')
            elif isinstance(value, str) and value:
                lines.append(f'\t"${key}" "{value}"')
    
    # Core textures
    add_param('basetexture', props.basetexture)
    add_param('bumpmap', props.bumpmap)
    
    # Color
    if props.color != (1.0, 1.0, 1.0):
        add_param('color2', props.color2)
    if props.alpha != 1.0:
        add_param('alpha', props.alpha)
    add_param('blendtintbybasealpha', props.blendtintbybasealpha, props.blendtintbybasealpha)
    
    # Phong
    add_param('phong', props.phong, props.phong)
    if props.phong:
        add_param('phongexponent', props.phongexponent)
        add_param('phongboost', props.phongboost)
        add_param('phongfresnelranges', props.phongfresnelranges)
        if props.phongtint != (1.0, 1.0, 1.0):
            add_param('phongtint', props.phongtint)
        add_param('phongalbedotint', props.phongalbedotint, props.phongalbedotint)
        add_param('phongexponenttexture', props.phongexponenttexture)
        add_param('basemapalphaphongmask', props.basemapalphaphongmask, props.basemapalphaphongmask)
    
    # Light warp
    add_param('lightwarptexture', props.lightwarptexture)
    add_param('phongwarptexture', props.phongwarptexture)
    
    # Environment map
    add_param('envmap', props.envmap)
    if props.envmap:
        if props.envmaptint != (1.0, 1.0, 1.0):
            add_param('envmaptint', props.envmaptint)
        add_param('envmapcontrast', props.envmapcontrast, props.envmapcontrast > 0)
        add_param('envmapsaturation', props.envmapsaturation, props.envmapsaturation != 1.0)
        add_param('envmapfresnel', props.envmapfresnel, props.envmapfresnel > 0)
        add_param('envmapmask', props.envmapmask)
        add_param('basealphaenvmapmask', props.basealphaenvmapmask, props.basealphaenvmapmask)
        add_param('normalmapalphaenvmapmask', props.normalmapalphaenvmapmask, props.normalmapalphaenvmapmask)
    
    # Self-illumination
    add_param('selfillum', props.selfillum, props.selfillum)
    if props.selfillum:
        if props.selfillumtint != (1.0, 1.0, 1.0):
            add_param('selfillumtint', props.selfillumtint)
        add_param('selfillummask', props.selfillummask)
    
    # Rim lighting
    add_param('rimlight', props.rimlight, props.rimlight)
    if props.rimlight:
        add_param('rimlightexponent', props.rimlightexponent)
        add_param('rimlightboost', props.rimlightboost)
    
    # Detail texture
    add_param('detail', props.detail)
    if props.detail:
        add_param('detailscale', props.detailscale)
        add_param('detailblendfactor', props.detailblendfactor)
        add_param('detailblendmode', props.detailblendmode)
    
    # Transparency
    add_param('translucent', props.translucent, props.translucent)
    add_param('alphatest', props.alphatest, props.alphatest)
    if props.alphatest:
        add_param('alphatestreference', props.alphatestreference)
    add_param('additive', props.additive, props.additive)
    
    # Misc
    add_param('halflambert', props.halflambert, props.halflambert)
    add_param('nocull', props.nocull, props.nocull)
    add_param('model', props.model, props.model)
    
    lines.append('}')
    return '\n'.join(lines)


# ============================================================================
# UI PANELS
# ============================================================================

class VLG_PT_MainPanel(Panel):
    """Main panel for VertexLitGeneric properties"""
    bl_label = "VertexLitGeneric"
    bl_idname = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        # Main action buttons
        row = layout.row(align=True)
        row.operator("vlg.apply_shader", icon='SHADING_RENDERED')
        row.operator("vlg.create_material", icon='ADD')
        
        row = layout.row(align=True)
        row.operator("vlg.import_vmt", icon='IMPORT')
        row.operator("vlg.export_vmt", icon='EXPORT')
        
        row = layout.row(align=True)
        row.operator("vlg.refresh_materials", icon='SHADING_RENDERED')
        row.operator("vlg.reload_vmt", icon='FILE_REFRESH')


class VLG_PT_TexturesPanel(Panel):
    """Textures sub-panel"""
    bl_label = "Textures"
    bl_idname = "VLG_PT_textures"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.prop(props, "basetexture")
        layout.prop(props, "bumpmap")
        
        # Texture transform
        box = layout.box()
        box.label(text="Base Texture Transform")
        box.prop(props, "basetexturetransform_scale")
        box.prop(props, "basetexturetransform_translate")
        box.prop(props, "basetexturetransform_rotate")


class VLG_PT_ColorPanel(Panel):
    """Color and modulation sub-panel"""
    bl_label = "Color & Modulation"
    bl_idname = "VLG_PT_color"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.prop(props, "color")
        layout.prop(props, "color2")
        layout.prop(props, "alpha")
        layout.prop(props, "blendtintbybasealpha")
        layout.prop(props, "blendtintcoloroverbase")


class VLG_PT_PhongPanel(Panel):
    """Phong specular sub-panel"""
    bl_label = "Phong Specular"
    bl_idname = "VLG_PT_phong"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw_header(self, context):
        mat = context.active_object.active_material
        props = mat.vlg_props
        self.layout.prop(props, "phong", text="")
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.active = props.phong
        
        layout.prop(props, "phongexponent")
        layout.prop(props, "phongboost")
        layout.prop(props, "phongtint")
        layout.prop(props, "phongfresnelranges")
        layout.prop(props, "phongalbedotint")
        layout.prop(props, "phongalbedoboost")
        layout.prop(props, "phongexponenttexture")
        layout.prop(props, "basemapalphaphongmask")
        layout.prop(props, "invertphongmask")
        layout.prop(props, "phongdisablehalflambert")
        
        layout.separator()
        layout.prop(props, "lightwarptexture")
        layout.prop(props, "phongwarptexture")


class VLG_PT_EnvMapPanel(Panel):
    """Environment map sub-panel"""
    bl_label = "Environment Map"
    bl_idname = "VLG_PT_envmap"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.prop(props, "envmap")
        layout.prop(props, "envmaptint")
        layout.prop(props, "envmapcontrast")
        layout.prop(props, "envmapsaturation")
        layout.prop(props, "envmapfresnel")
        layout.prop(props, "envmapmask")
        layout.prop(props, "basealphaenvmapmask")
        layout.prop(props, "normalmapalphaenvmapmask")


class VLG_PT_SelfIllumPanel(Panel):
    """Self-illumination sub-panel"""
    bl_label = "Self-Illumination"
    bl_idname = "VLG_PT_selfillum"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw_header(self, context):
        mat = context.active_object.active_material
        props = mat.vlg_props
        self.layout.prop(props, "selfillum", text="")
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.active = props.selfillum
        
        layout.prop(props, "selfillumtint")
        layout.prop(props, "selfillummask")
        layout.prop(props, "selfillumfresnel")
        
        if props.selfillumfresnel:
            layout.prop(props, "selfillumfresnelminmaxexp")


class VLG_PT_RimLightPanel(Panel):
    """Rim lighting sub-panel"""
    bl_label = "Rim Lighting"
    bl_idname = "VLG_PT_rimlight"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw_header(self, context):
        mat = context.active_object.active_material
        props = mat.vlg_props
        self.layout.prop(props, "rimlight", text="")
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.active = props.rimlight
        
        layout.prop(props, "rimlightexponent")
        layout.prop(props, "rimlightboost")
        layout.prop(props, "rimmask")


class VLG_PT_DetailPanel(Panel):
    """Detail texture sub-panel"""
    bl_label = "Detail Texture"
    bl_idname = "VLG_PT_detail"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.prop(props, "detail")
        
        if props.detail:
            layout.prop(props, "detailscale")
            layout.prop(props, "detailblendfactor")
            layout.prop(props, "detailblendmode")
            layout.prop(props, "detailtint")


class VLG_PT_TransparencyPanel(Panel):
    """Transparency sub-panel"""
    bl_label = "Transparency"
    bl_idname = "VLG_PT_transparency"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.prop(props, "translucent")
        layout.prop(props, "alphatest")
        
        if props.alphatest:
            layout.prop(props, "alphatestreference")
        
        layout.prop(props, "additive")


class VLG_PT_MiscPanel(Panel):
    """Miscellaneous sub-panel"""
    bl_label = "Miscellaneous"
    bl_idname = "VLG_PT_misc"
    bl_parent_id = "VLG_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        mat = context.active_object.active_material
        props = mat.vlg_props
        
        layout.prop(props, "halflambert")
        layout.prop(props, "nocull")
        layout.prop(props, "model")
        
        layout.separator()
        layout.prop(props, "fix_wetness")


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    VLGMaterialProperties,
    VLG_OT_ApplyShader,
    VLG_OT_CreateMaterial,
    VLG_OT_ImportVMT,
    VLG_OT_ExportVMT,
    VLG_OT_RefreshMaterials,
    VLG_OT_ReloadVMT,
    VLG_PT_MainPanel,
    VLG_PT_TexturesPanel,
    VLG_PT_ColorPanel,
    VLG_PT_PhongPanel,
    VLG_PT_EnvMapPanel,
    VLG_PT_SelfIllumPanel,
    VLG_PT_RimLightPanel,
    VLG_PT_DetailPanel,
    VLG_PT_TransparencyPanel,
    VLG_PT_MiscPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Material.vlg_props = PointerProperty(type=VLGMaterialProperties)
    
    # Register SourceIO integration if available
    if sourceio_integration is not None:
        sourceio_integration.register_sourceio_integration()
        # Add to import menu
        bpy.types.TOPBAR_MT_file_import.append(sourceio_integration.draw_sourceio_menu)


def unregister():
    # Unregister SourceIO integration
    if sourceio_integration is not None:
        try:
            bpy.types.TOPBAR_MT_file_import.remove(sourceio_integration.draw_sourceio_menu)
        except:
            pass
        sourceio_integration.unregister_sourceio_integration()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Material.vlg_props


if __name__ == "__main__":
    register()
