# VertexLitGeneric Shader Node Builder
# Advanced node group creation for accurate Source Engine lighting recreation

import bpy
from mathutils import Vector


def create_half_lambert_node_group():
    """
    Create Half-Lambert diffuse lighting node group.
    Source Engine's Half-Lambert wraps diffuse lighting around surfaces more.
    
    Formula: HalfLambert = (NdotL * 0.5 + 0.5) ^ 2
    """
    group_name = "VLG_HalfLambert"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Create interface
    group.interface.new_socket(name="Normal", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Light Dir", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Half-Lambert", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Diffuse", in_out='OUTPUT', socket_type='NodeSocketFloat')
    
    nodes = group.nodes
    links = group.links
    
    # Input/Output
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-600, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # Dot product: N . L
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.location = (-400, 0)
    
    # Scale by 0.5
    scale = nodes.new('ShaderNodeMath')
    scale.operation = 'MULTIPLY'
    scale.location = (-200, 0)
    scale.inputs[1].default_value = 0.5
    
    # Add 0.5
    add = nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.location = (0, 0)
    add.inputs[1].default_value = 0.5
    
    # Square (power 2)
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    power.location = (200, 0)
    power.inputs[1].default_value = 2.0
    
    # Standard Lambert (just clamp NdotL)
    clamp = nodes.new('ShaderNodeClamp')
    clamp.location = (-200, -150)
    clamp.inputs['Min'].default_value = 0.0
    clamp.inputs['Max'].default_value = 1.0
    
    # Mix between standard and half-lambert
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'FLOAT'
    mix.location = (400, 0)
    
    # Connect
    links.new(input_node.outputs['Normal'], dot.inputs[0])
    links.new(input_node.outputs['Light Dir'], dot.inputs[1])
    links.new(dot.outputs['Value'], scale.inputs[0])
    links.new(scale.outputs[0], add.inputs[0])
    links.new(add.outputs[0], power.inputs[0])
    links.new(dot.outputs['Value'], clamp.inputs['Value'])
    links.new(input_node.outputs['Half-Lambert'], mix.inputs['Factor'])
    links.new(clamp.outputs['Result'], mix.inputs['A'])
    links.new(power.outputs[0], mix.inputs['B'])
    links.new(mix.outputs['Result'], output_node.inputs['Diffuse'])
    
    return group


def create_phong_fresnel_node_group():
    """
    Create Phong Fresnel remapping node group.
    Source Engine uses $phongfresnelranges [min mid max] to remap fresnel.
    
    Formula: smoothstep(min, mid, 1-NdotV) * max
    """
    group_name = "VLG_PhongFresnel"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="NdotV", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Min", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Mid", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Max", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Fresnel", in_out='OUTPUT', socket_type='NodeSocketFloat')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-600, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # 1 - NdotV
    invert = nodes.new('ShaderNodeMath')
    invert.operation = 'SUBTRACT'
    invert.location = (-400, 0)
    invert.inputs[0].default_value = 1.0
    
    # Map range (smoothstep from min to mid)
    map_range = nodes.new('ShaderNodeMapRange')
    map_range.location = (-100, 0)
    map_range.interpolation_type = 'SMOOTHSTEP'
    map_range.inputs['To Min'].default_value = 0.0
    map_range.inputs['To Max'].default_value = 1.0
    
    # Multiply by max
    multiply = nodes.new('ShaderNodeMath')
    multiply.operation = 'MULTIPLY'
    multiply.location = (200, 0)
    
    # Connect
    links.new(input_node.outputs['NdotV'], invert.inputs[1])
    links.new(invert.outputs[0], map_range.inputs['Value'])
    links.new(input_node.outputs['Min'], map_range.inputs['From Min'])
    links.new(input_node.outputs['Mid'], map_range.inputs['From Max'])
    links.new(map_range.outputs['Result'], multiply.inputs[0])
    links.new(input_node.outputs['Max'], multiply.inputs[1])
    links.new(multiply.outputs[0], output_node.inputs['Fresnel'])
    
    return group


def create_rim_light_node_group():
    """
    Create rim lighting node group.
    Source Engine rim light: (1 - NdotV)^exponent * boost
    
    Can be masked by $rimmask from phong exponent texture alpha.
    """
    group_name = "VLG_RimLight"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="Normal", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="View Vector", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Exponent", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Boost", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Mask", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Rim", in_out='OUTPUT', socket_type='NodeSocketFloat')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-600, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # Dot product N.V
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.location = (-400, 0)
    
    # Clamp 0-1
    clamp = nodes.new('ShaderNodeClamp')
    clamp.location = (-200, 0)
    
    # 1 - NdotV
    invert = nodes.new('ShaderNodeMath')
    invert.operation = 'SUBTRACT'
    invert.location = (0, 0)
    invert.inputs[0].default_value = 1.0
    
    # Power by exponent
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    power.location = (200, 0)
    
    # Multiply by boost
    boost_mult = nodes.new('ShaderNodeMath')
    boost_mult.operation = 'MULTIPLY'
    boost_mult.location = (350, 0)
    
    # Multiply by mask
    mask_mult = nodes.new('ShaderNodeMath')
    mask_mult.operation = 'MULTIPLY'
    mask_mult.location = (500, 0)
    
    # Connect
    links.new(input_node.outputs['Normal'], dot.inputs[0])
    links.new(input_node.outputs['View Vector'], dot.inputs[1])
    links.new(dot.outputs['Value'], clamp.inputs['Value'])
    links.new(clamp.outputs['Result'], invert.inputs[1])
    links.new(invert.outputs[0], power.inputs[0])
    links.new(input_node.outputs['Exponent'], power.inputs[1])
    links.new(power.outputs[0], boost_mult.inputs[0])
    links.new(input_node.outputs['Boost'], boost_mult.inputs[1])
    links.new(boost_mult.outputs[0], mask_mult.inputs[0])
    links.new(input_node.outputs['Mask'], mask_mult.inputs[1])
    links.new(mask_mult.outputs[0], output_node.inputs['Rim'])
    
    return group


def create_envmap_processing_node_group():
    """
    Create environment map processing node group.
    Source Engine applies contrast and saturation to envmap samples.
    
    $envmapcontrast: lerp(envmap, envmap*envmap, contrast)
    $envmapsaturation: lerp(grayscale, envmap, saturation)
    """
    group_name = "VLG_EnvmapProcess"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="Envmap Color", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Tint", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Contrast", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Saturation", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Result", in_out='OUTPUT', socket_type='NodeSocketColor')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-800, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # Apply tint
    tint_mult = nodes.new('ShaderNodeMix')
    tint_mult.data_type = 'RGBA'
    tint_mult.blend_type = 'MULTIPLY'
    tint_mult.location = (-500, 0)
    tint_mult.inputs['Factor'].default_value = 1.0
    
    # Square for contrast
    contrast_square = nodes.new('ShaderNodeMix')
    contrast_square.data_type = 'RGBA'
    contrast_square.blend_type = 'MULTIPLY'
    contrast_square.location = (-200, -100)
    contrast_square.inputs['Factor'].default_value = 1.0
    
    # Lerp between normal and squared (contrast)
    contrast_mix = nodes.new('ShaderNodeMix')
    contrast_mix.data_type = 'RGBA'
    contrast_mix.location = (0, 0)
    
    # Convert to grayscale for saturation
    # Luminance: 0.299*R + 0.587*G + 0.114*B
    separate = nodes.new('ShaderNodeSeparateColor')
    separate.location = (-200, -300)
    
    lum_r = nodes.new('ShaderNodeMath')
    lum_r.operation = 'MULTIPLY'
    lum_r.location = (0, -250)
    lum_r.inputs[1].default_value = 0.299
    
    lum_g = nodes.new('ShaderNodeMath')
    lum_g.operation = 'MULTIPLY'
    lum_g.location = (0, -350)
    lum_g.inputs[1].default_value = 0.587
    
    lum_b = nodes.new('ShaderNodeMath')
    lum_b.operation = 'MULTIPLY'
    lum_b.location = (0, -450)
    lum_b.inputs[1].default_value = 0.114
    
    add_rg = nodes.new('ShaderNodeMath')
    add_rg.operation = 'ADD'
    add_rg.location = (150, -300)
    
    add_rgb = nodes.new('ShaderNodeMath')
    add_rgb.operation = 'ADD'
    add_rgb.location = (300, -350)
    
    # Convert luminance to grayscale color
    gray_combine = nodes.new('ShaderNodeCombineColor')
    gray_combine.location = (200, -450)
    
    # Lerp between grayscale and color (saturation)
    sat_mix = nodes.new('ShaderNodeMix')
    sat_mix.data_type = 'RGBA'
    sat_mix.location = (400, 0)
    
    # Connect tint
    links.new(input_node.outputs['Envmap Color'], tint_mult.inputs['A'])
    links.new(input_node.outputs['Tint'], tint_mult.inputs['B'])
    
    # Connect contrast
    links.new(tint_mult.outputs['Result'], contrast_square.inputs['A'])
    links.new(tint_mult.outputs['Result'], contrast_square.inputs['B'])
    links.new(input_node.outputs['Contrast'], contrast_mix.inputs['Factor'])
    links.new(tint_mult.outputs['Result'], contrast_mix.inputs['A'])
    links.new(contrast_square.outputs['Result'], contrast_mix.inputs['B'])
    
    # Connect saturation
    links.new(contrast_mix.outputs['Result'], separate.inputs['Color'])
    links.new(separate.outputs['Red'], lum_r.inputs[0])
    links.new(separate.outputs['Green'], lum_g.inputs[0])
    links.new(separate.outputs['Blue'], lum_b.inputs[0])
    links.new(lum_r.outputs[0], add_rg.inputs[0])
    links.new(lum_g.outputs[0], add_rg.inputs[1])
    links.new(add_rg.outputs[0], add_rgb.inputs[0])
    links.new(lum_b.outputs[0], add_rgb.inputs[1])
    links.new(add_rgb.outputs[0], gray_combine.inputs['Red'])
    links.new(add_rgb.outputs[0], gray_combine.inputs['Green'])
    links.new(add_rgb.outputs[0], gray_combine.inputs['Blue'])
    
    links.new(input_node.outputs['Saturation'], sat_mix.inputs['Factor'])
    links.new(gray_combine.outputs['Color'], sat_mix.inputs['A'])
    links.new(contrast_mix.outputs['Result'], sat_mix.inputs['B'])
    
    links.new(sat_mix.outputs['Result'], output_node.inputs['Result'])
    
    return group


def create_detail_blend_node_group(blend_mode=0):
    """
    Create detail texture blending node group.
    Source Engine detail blend modes:
    0: Mod2X (multiply by 2, gray = no change)
    1: Additive
    2: Alpha blend
    3: Crossfade/Lerp
    4: Multiply
    5: Add self-illum
    """
    group_name = f"VLG_DetailBlend_{blend_mode}"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="Base Color", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Detail Color", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Detail Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Blend Factor", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Detail Tint", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Result", in_out='OUTPUT', socket_type='NodeSocketColor')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-600, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # Apply detail tint
    tint = nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.location = (-300, 0)
    tint.inputs['Factor'].default_value = 1.0
    
    links.new(input_node.outputs['Detail Color'], tint.inputs['A'])
    links.new(input_node.outputs['Detail Tint'], tint.inputs['B'])
    
    if blend_mode == 0:  # Mod2X
        # detail * 2, then multiply with base
        # gray (0.5) becomes 1.0, so no change
        scale2 = nodes.new('ShaderNodeMix')
        scale2.data_type = 'RGBA'
        scale2.blend_type = 'ADD'
        scale2.location = (-100, 0)
        scale2.inputs['Factor'].default_value = 1.0
        
        mult = nodes.new('ShaderNodeMix')
        mult.data_type = 'RGBA'
        mult.blend_type = 'MULTIPLY'
        mult.location = (100, 0)
        mult.inputs['Factor'].default_value = 1.0
        
        final_mix = nodes.new('ShaderNodeMix')
        final_mix.data_type = 'RGBA'
        final_mix.location = (300, 0)
        
        links.new(tint.outputs['Result'], scale2.inputs['A'])
        links.new(tint.outputs['Result'], scale2.inputs['B'])
        links.new(input_node.outputs['Base Color'], mult.inputs['A'])
        links.new(scale2.outputs['Result'], mult.inputs['B'])
        links.new(input_node.outputs['Blend Factor'], final_mix.inputs['Factor'])
        links.new(input_node.outputs['Base Color'], final_mix.inputs['A'])
        links.new(mult.outputs['Result'], final_mix.inputs['B'])
        links.new(final_mix.outputs['Result'], output_node.inputs['Result'])
        
    elif blend_mode == 1:  # Additive
        add = nodes.new('ShaderNodeMix')
        add.data_type = 'RGBA'
        add.blend_type = 'ADD'
        add.location = (0, 0)
        
        scale = nodes.new('ShaderNodeMix')
        scale.data_type = 'RGBA'
        scale.location = (-100, -100)
        
        links.new(input_node.outputs['Blend Factor'], scale.inputs['Factor'])
        scale.inputs['A'].default_value = (0, 0, 0, 1)
        links.new(tint.outputs['Result'], scale.inputs['B'])
        links.new(input_node.outputs['Base Color'], add.inputs['A'])
        links.new(scale.outputs['Result'], add.inputs['B'])
        add.inputs['Factor'].default_value = 1.0
        links.new(add.outputs['Result'], output_node.inputs['Result'])
        
    elif blend_mode == 2:  # Alpha blend
        alpha_blend = nodes.new('ShaderNodeMix')
        alpha_blend.data_type = 'RGBA'
        alpha_blend.location = (100, 0)
        
        factor_mult = nodes.new('ShaderNodeMath')
        factor_mult.operation = 'MULTIPLY'
        factor_mult.location = (-100, -100)
        
        links.new(input_node.outputs['Detail Alpha'], factor_mult.inputs[0])
        links.new(input_node.outputs['Blend Factor'], factor_mult.inputs[1])
        links.new(factor_mult.outputs[0], alpha_blend.inputs['Factor'])
        links.new(input_node.outputs['Base Color'], alpha_blend.inputs['A'])
        links.new(tint.outputs['Result'], alpha_blend.inputs['B'])
        links.new(alpha_blend.outputs['Result'], output_node.inputs['Result'])
        
    elif blend_mode == 3:  # Crossfade/Lerp
        lerp = nodes.new('ShaderNodeMix')
        lerp.data_type = 'RGBA'
        lerp.location = (100, 0)
        
        links.new(input_node.outputs['Blend Factor'], lerp.inputs['Factor'])
        links.new(input_node.outputs['Base Color'], lerp.inputs['A'])
        links.new(tint.outputs['Result'], lerp.inputs['B'])
        links.new(lerp.outputs['Result'], output_node.inputs['Result'])
        
    elif blend_mode == 4:  # Multiply
        mult = nodes.new('ShaderNodeMix')
        mult.data_type = 'RGBA'
        mult.blend_type = 'MULTIPLY'
        mult.location = (0, 0)
        
        final_mix = nodes.new('ShaderNodeMix')
        final_mix.data_type = 'RGBA'
        final_mix.location = (200, 0)
        
        links.new(input_node.outputs['Base Color'], mult.inputs['A'])
        links.new(tint.outputs['Result'], mult.inputs['B'])
        mult.inputs['Factor'].default_value = 1.0
        links.new(input_node.outputs['Blend Factor'], final_mix.inputs['Factor'])
        links.new(input_node.outputs['Base Color'], final_mix.inputs['A'])
        links.new(mult.outputs['Result'], final_mix.inputs['B'])
        links.new(final_mix.outputs['Result'], output_node.inputs['Result'])
    
    else:  # Default to mod2x
        links.new(input_node.outputs['Base Color'], output_node.inputs['Result'])
    
    return group


def create_selfillum_fresnel_node_group():
    """
    Create self-illumination fresnel node group.
    Source Engine $selfillumfresnel with $selfillumfresnelminmaxexp
    
    Formula: clamp((NdotV^exp * scale) + bias, 0, 1)
    """
    group_name = "VLG_SelfIllumFresnel"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="Normal", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="View Vector", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Min (Bias)", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Max (Scale)", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Exponent", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Fresnel", in_out='OUTPUT', socket_type='NodeSocketFloat')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-600, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (600, 0)
    
    # N.V
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.location = (-400, 0)
    
    # Clamp 0-1
    clamp1 = nodes.new('ShaderNodeClamp')
    clamp1.location = (-200, 0)
    
    # Power
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    power.location = (0, 0)
    
    # Scale
    scale = nodes.new('ShaderNodeMath')
    scale.operation = 'MULTIPLY'
    scale.location = (150, 0)
    
    # Add bias
    add = nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.location = (300, 0)
    
    # Final clamp
    clamp2 = nodes.new('ShaderNodeClamp')
    clamp2.location = (450, 0)
    
    # Connect
    links.new(input_node.outputs['Normal'], dot.inputs[0])
    links.new(input_node.outputs['View Vector'], dot.inputs[1])
    links.new(dot.outputs['Value'], clamp1.inputs['Value'])
    links.new(clamp1.outputs['Result'], power.inputs[0])
    links.new(input_node.outputs['Exponent'], power.inputs[1])
    links.new(power.outputs[0], scale.inputs[0])
    links.new(input_node.outputs['Max (Scale)'], scale.inputs[1])
    links.new(scale.outputs[0], add.inputs[0])
    links.new(input_node.outputs['Min (Bias)'], add.inputs[1])
    links.new(add.outputs[0], clamp2.inputs['Value'])
    links.new(clamp2.outputs['Result'], output_node.inputs['Fresnel'])
    
    return group


def create_light_warp_node_group():
    """
    Create light warp node group.
    Source Engine $lightwarptexture remaps diffuse lighting for toon-style effects.
    
    The texture is sampled using the diffuse term as the U coordinate.
    """
    group_name = "VLG_LightWarp"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="Diffuse", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Warp Texture", in_out='INPUT', socket_type='NodeSocketColor')
    group.interface.new_socket(name="Warped Diffuse", in_out='OUTPUT', socket_type='NodeSocketFloat')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-400, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (400, 0)
    
    # The warp texture is already sampled, so we just use it as the diffuse value
    # In practice, you'd combine the UV with the diffuse value
    # For Blender, we can use a color ramp as an approximation
    
    # Separate to get red channel (usually sufficient for 1D warp)
    separate = nodes.new('ShaderNodeSeparateColor')
    separate.location = (0, 0)
    
    # Or we could just pass through the diffuse if no warp texture
    # For now, use the warp texture's red channel
    
    links.new(input_node.outputs['Warp Texture'], separate.inputs['Color'])
    links.new(separate.outputs['Red'], output_node.inputs['Warped Diffuse'])
    
    return group


def create_phong_specular_node_group():
    """
    Create Phong specular highlighting node group.
    Source Engine Phong: (R.V)^exponent * boost * mask
    
    Where R = reflect(-L, N) and V = view direction
    """
    group_name = "VLG_PhongSpecular"
    
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]
    
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    # Interface
    group.interface.new_socket(name="Normal", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="View Vector", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Light Vector", in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket(name="Exponent", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Boost", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Mask", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Fresnel Factor", in_out='INPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket(name="Specular", in_out='OUTPUT', socket_type='NodeSocketFloat')
    
    nodes = group.nodes
    links = group.links
    
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-800, 0)
    
    output_node = nodes.new('NodeGroupOutput')
    output_node.location = (800, 0)
    
    # Negate light vector
    negate = nodes.new('ShaderNodeVectorMath')
    negate.operation = 'SCALE'
    negate.location = (-600, 0)
    negate.inputs['Scale'].default_value = -1.0
    
    # Reflect
    reflect = nodes.new('ShaderNodeVectorMath')
    reflect.operation = 'REFLECT'
    reflect.location = (-400, 0)
    
    # R.V
    dot = nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.location = (-200, 0)
    
    # Clamp
    clamp = nodes.new('ShaderNodeClamp')
    clamp.location = (0, 0)
    
    # Power by exponent
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    power.location = (150, 0)
    
    # Multiply by boost
    boost = nodes.new('ShaderNodeMath')
    boost.operation = 'MULTIPLY'
    boost.location = (300, 0)
    
    # Multiply by mask
    mask = nodes.new('ShaderNodeMath')
    mask.operation = 'MULTIPLY'
    mask.location = (450, 0)
    
    # Multiply by fresnel
    fresnel = nodes.new('ShaderNodeMath')
    fresnel.operation = 'MULTIPLY'
    fresnel.location = (600, 0)
    
    # Connect
    links.new(input_node.outputs['Light Vector'], negate.inputs['Vector'])
    links.new(negate.outputs['Vector'], reflect.inputs[0])
    links.new(input_node.outputs['Normal'], reflect.inputs[1])
    links.new(reflect.outputs['Vector'], dot.inputs[0])
    links.new(input_node.outputs['View Vector'], dot.inputs[1])
    links.new(dot.outputs['Value'], clamp.inputs['Value'])
    links.new(clamp.outputs['Result'], power.inputs[0])
    links.new(input_node.outputs['Exponent'], power.inputs[1])
    links.new(power.outputs[0], boost.inputs[0])
    links.new(input_node.outputs['Boost'], boost.inputs[1])
    links.new(boost.outputs[0], mask.inputs[0])
    links.new(input_node.outputs['Mask'], mask.inputs[1])
    links.new(mask.outputs[0], fresnel.inputs[0])
    links.new(input_node.outputs['Fresnel Factor'], fresnel.inputs[1])
    links.new(fresnel.outputs[0], output_node.inputs['Specular'])
    
    return group


def create_all_vlg_node_groups():
    """Create all VertexLitGeneric node groups."""
    create_half_lambert_node_group()
    create_phong_fresnel_node_group()
    create_rim_light_node_group()
    create_envmap_processing_node_group()
    create_selfillum_fresnel_node_group()
    create_light_warp_node_group()
    create_phong_specular_node_group()
    
    # Create all detail blend modes
    for mode in range(5):
        create_detail_blend_node_group(mode)
    
    print("All VertexLitGeneric node groups created successfully.")


# Register function to be called from main __init__.py
def register():
    pass


def unregister():
    pass
