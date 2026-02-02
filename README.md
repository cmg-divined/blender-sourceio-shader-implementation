# Blender VertexLitGeneric Shader

A Blender addon that replicates Source Engine's VertexLitGeneric shader for imported models. This allows Source 1 models (from Garry's Mod, Half-Life 2, Counter-Strike: Source, etc.) to render with accurate materials in Blender.
Convert textures to tga with VTFEdit for faster load times please in the same directories.

## Features

- Parses VMT material files and extracts all VertexLitGeneric parameters
- Implements Source Engine lighting model including:
  - Half-Lambert diffuse shading
  - Phong specular with fresnel ranges
  - Rim lighting
  - Environment map reflections
  - Self-illumination
  - Normal mapping
- Handles transparency ($translucent, $alphatest)
- Automatic VTF texture conversion
- SourceIO integration for MDL imports with VLG materials

## Requirements

- **Blender 4.0+** or **Blender 5.0**
- **SourceIO** addon (required for MDL import integration)

## Installation

1. Download this addon as a ZIP file
2. In Blender: Edit > Preferences > Add-ons > Install
3. Select the ZIP file and enable the addon
4. Ensure SourceIO is also installed and enabled

## Usage

### Importing MDL Models

File > Import > Source MDL (Softlamps VLG)

This imports Source Engine MDL models with the VertexLitGeneric shader applied automatically. The importer reads VMT files and configures materials based on their parameters.

### Manual Material Setup

1. Select an object
2. Open the Material Properties panel
3. Expand the "VertexLitGeneric Properties" section
4. Configure parameters and texture paths
5. Click "Apply VLG Shader"

### Importing VMT Files

In the Material Properties panel, click "Import VMT" to load material settings from a VMT file.

## VMT Parameters Supported

| Parameter | Description |
|-----------|-------------|
| $basetexture | Diffuse/albedo texture |
| $bumpmap | Normal map |
| $phongexponenttexture | Phong exponent mask |
| $envmap | Environment map |
| $envmapmask | Environment map mask |
| $phong | Enable phong specular |
| $phongexponent | Specular exponent |
| $phongboost | Specular intensity |
| $phongfresnelranges | Fresnel control [min, mid, max] |
| $phongtint | Specular tint color |
| $phongalbedotint | Tint specular by albedo |
| $rimlight | Enable rim lighting |
| $rimlightexponent | Rim light falloff |
| $rimlightboost | Rim light intensity |
| $halflambert | Use Half-Lambert diffuse |
| $selfillum | Enable self-illumination |
| $selfillumtint | Self-illumination color |
| $translucent | Enable alpha blending |
| $alphatest | Enable alpha testing |
| $color2 | Color modulation |
| $nocull | Disable backface culling |

## Notes

- The shader uses Blender's Principled BSDF as a base, with custom node math to approximate Source Engine lighting
- Works in both Eevee and Cycles render engines
- Texture paths are resolved using SourceIO's content manager when importing MDLs

## License

MIT License

