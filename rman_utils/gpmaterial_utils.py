from ..rman_utils import color_utils
from ..rman_utils import texture_utils
from ..rman_utils import filepath_utils
from .. import txmanager3
import math

def gp_material_stroke_solid(mat, rman, rman_sg_material, handle):
    gp_mat = mat.grease_pencil

    bxdf_handle = '%s-PxrConstant' % handle
    bxdf = rman.SGManager.RixSGShader("Bxdf", "PxrConstant", bxdf_handle)
    
    col =  gp_mat.color[:3]
    col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.color[3]

    params = bxdf.params
    params.SetColor('emitColor', col)     
    params.SetFloat('presence', alpha)
    rman_sg_material.sg_node.SetBxdf([bxdf]) 

def gp_material_stroke_texture(mat, rman, rman_sg_material, handle):
    gp_mat = mat.grease_pencil
    col =  gp_mat.color[:3]
    col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.color[3]

    bl_image = gp_mat.stroke_image
    mat_sg_nodes = []

    bxdf_handle = '%s-PxrConstant' % handle
    bxdf = rman.SGManager.RixSGShader("Bxdf", "PxrConstant", bxdf_handle)   

    if not bl_image:
        params = bxdf.params
        params.SetColor('emitColor', [0.0, 0.0, 0.0])     
        rman_sg_material.sg_node.SetBxdf([bxdf]) 
    else:
        real_file = filepath_utils.get_real_path(bl_image.filepath)

        manifold_handle = '%s-PxrManifold2D' % handle
        manifold = rman.SGManager.RixSGShader("Pattern", "PxrManifold2D", manifold_handle) 
        params = manifold.params    
        params.SetInteger("invertT", 1)  

        mat_sg_nodes.append(manifold)          

        texture_handle = '%s-PxrTexture' % handle

        nodeID = '%s|filename|%s' % (texture_handle, real_file)
        output_tex = texture_utils.get_txmanager().get_txfile_from_id(nodeID)
        if output_tex == '':  
            txfile = texture_utils.get_txmanager().txmanager.add_texture(nodeID, real_file) 
            if txfile.state in (txmanager3.STATE_EXISTS, txmanager3.STATE_IS_TEX):
                output_tex = txfile.get_output_texture()
            else:
                output_tex = get_txmanager().get_placeholder_tex() 

        texture = rman.SGManager.RixSGShader("Pattern", "PxrTexture", texture_handle) 
        mat_sg_nodes.append(texture)
        params = texture.params

        params.SetString("filename", output_tex)
        params.SetInteger("linearize", 1)
        params.ReferenceStruct("manifold", '%s:result' % manifold_handle)       

        params = bxdf.params
        if gp_mat.use_stroke_pattern:
            params.SetColor("emitColor", col)
        elif gp_mat.use_stroke_texture_mix:
            mix_handle = '%s-PxrToMix' % handle
            mix = rman.SGManager.RixSGShader("Pattern", "PxrMix", mix_handle) 
            mix.params.ReferenceColor("color1", '%s:resultRGB' % texture_handle)                                             
            mix.params.SetColor("color2", col)
            mix.params.SetFloat("mix", gp_mat.mix_stroke_factor)    
            mat_sg_nodes.append(mix)  
            params.ReferenceColor("emitColor", '%s:resultRGB' % mix_handle)
        else:
            params.ReferenceColor("emitColor", '%s:resultRGB' % texture_handle)
        params.ReferenceFloat("presence", '%s:resultA' % texture_handle)
        mat_sg_nodes.append(bxdf)
        rman_sg_material.sg_node.SetBxdf(mat_sg_nodes)    
    

def gp_material_fill_texture(mat, rman, rman_sg_material, handle):
    gp_mat = mat.grease_pencil
    col = gp_mat.fill_color[:3]
    col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.fill_color[3]
    mix_color = gp_mat.mix_color[:3]
    mix_alpha = gp_mat.mix_color[3]

    bl_image = gp_mat.fill_image
    mat_sg_nodes = []

    bxdf_handle = '%s-PxrConstant' % handle
    bxdf = rman.SGManager.RixSGShader("Bxdf", "PxrConstant", bxdf_handle)   

    if not bl_image:
        params = bxdf.params
        params.SetColor('emitColor', [0.0, 0.0, 0.0])     
        rman_sg_material.sg_node.SetBxdf([bxdf]) 
    else:
        real_file = filepath_utils.get_real_path(bl_image.filepath)

        manifold_handle = '%s-PxrManifold2D' % handle
        manifold = rman.SGManager.RixSGShader("Pattern", "PxrManifold2D", manifold_handle) 
        params = manifold.params 
        params.SetFloat("scaleS", gp_mat.texture_scale[0])
        params.SetFloat("scaleT", gp_mat.texture_scale[1])   
        params.SetFloat("angle", -math.degrees(gp_mat.texture_angle))
        params.SetFloat("offsetS", gp_mat.texture_offset[0]) 
        params.SetFloat("offsetT", gp_mat.texture_offset[1])         

        params.SetInteger("invertT", 1)  

        mat_sg_nodes.append(manifold)          

        texture_handle = '%s-PxrTexture' % handle

        nodeID = '%s|filename|%s' % (texture_handle, real_file)
        output_tex = texture_utils.get_txmanager().get_txfile_from_id(nodeID)
        if output_tex == '':  
            txfile = texture_utils.get_txmanager().txmanager.add_texture(nodeID, real_file) 
            if txfile.state in (txmanager3.STATE_EXISTS, txmanager3.STATE_IS_TEX):
                output_tex = txfile.get_output_texture()
            else:
                output_tex = get_txmanager().get_placeholder_tex() 

        texture = rman.SGManager.RixSGShader("Pattern", "PxrTexture", texture_handle) 
        mat_sg_nodes.append(texture)
        params = texture.params

        params.SetString("filename", output_tex)
        params.SetInteger("linearize", 1)
        params.ReferenceStruct("manifold", '%s:result' % manifold_handle)       

        params = bxdf.params
        if gp_mat.use_fill_pattern:
            params.SetColor("emitColor", col)
        elif gp_mat.use_fill_texture_mix:
            mix_handle = '%s-PxrToMix' % handle
            mix = rman.SGManager.RixSGShader("Pattern", "PxrMix", mix_handle) 
            mix.params.ReferenceColor("color1", '%s:resultRGB' % texture_handle)                                             
            mix.params.SetColor("color2", col)
            mix.params.SetFloat("mix", gp_mat.mix_factor)    
            mat_sg_nodes.append(mix)  
            params.ReferenceColor("emitColor", '%s:resultRGB' % mix_handle)
        else:
            params.ReferenceColor("emitColor", '%s:resultRGB' % texture_handle)
        params.ReferenceFloat("presence", '%s:resultA' % texture_handle)
        mat_sg_nodes.append(bxdf)
        rman_sg_material.sg_node.SetBxdf(mat_sg_nodes)

def gp_material_fill_checker(mat, rman, rman_sg_material, handle):
    gp_mat = mat.grease_pencil
    col = gp_mat.fill_color[:3]
    col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.fill_color[3]
    mix_color = gp_mat.mix_color[:3]
    mix_alpha = gp_mat.mix_color[3]

    bxdf_handle = '%s-PxrConstant' % handle
    bxdf = rman.SGManager.RixSGShader("Bxdf", "PxrConstant", bxdf_handle) 

    manifold_handle = '%s-PxrManifold2D' % handle
    manifold = rman.SGManager.RixSGShader("Pattern", "PxrManifold2D", manifold_handle) 
    params = manifold.params 
    params.SetFloat("scaleS", (1/gp_mat.pattern_gridsize) * gp_mat.pattern_scale[0])
    params.SetFloat("scaleT", (1/gp_mat.pattern_gridsize) * gp_mat.pattern_scale[1])  
    params.SetFloat("angle", -math.degrees(gp_mat.pattern_angle)) 
    #params.SetFloat("offsetS", gp_mat.pattern_shift[0]) 
    #params.SetFloat("offsetT", gp_mat.pattern_shift[1])  
    params.SetInteger("invertT", 0)     

    checker_handle = '%s-PxrChecker' % handle
    checker = rman.SGManager.RixSGShader("Pattern", "PxrChecker", checker_handle) 
    params = checker.params
    params.SetColor("colorA", col)
    params.SetColor("colorB", mix_color)
    params.ReferenceStruct("manifold", '%s:result' % manifold_handle)

    checker2_handle = '%s-PxrChecker2' % handle
    checker2 = rman.SGManager.RixSGShader("Pattern", "PxrChecker", checker2_handle) 
    params = checker2.params
    params.SetColor("colorA", [0.0, 0.0, 0.0])
    params.SetColor("colorB", [1.0, 1.0, 1.0])                
    params.ReferenceStruct("manifold", '%s:result' % manifold_handle)                

    float3_1_handle = '%s-PxrToFloat3_1' % handle
    float3_1 = rman.SGManager.RixSGShader("Pattern", "PxrToFloat3", float3_1_handle) 
    params = float3_1.params 
    params.SetFloat("input", alpha)  

    float3_2_handle = '%s-PxrToFloat3_2' % handle
    float3_2 = rman.SGManager.RixSGShader("Pattern", "PxrToFloat3", float3_2_handle) 
    params = float3_2.params 
    params.SetFloat("input", mix_alpha) 

    mix_handle = '%s-PxrToMix' % handle
    mix = rman.SGManager.RixSGShader("Pattern", "PxrMix", mix_handle) 
    params = mix.params 
    params.ReferenceColor("color1", '%s:resultRGB' % float3_1_handle)                                             
    params.ReferenceColor("color2", '%s:resultRGB' % float3_2_handle)
    params.ReferenceFloat("mix", '%s:resultR' % checker2_handle )

    params = bxdf.params
    params.ReferenceColor("emitColor", '%s:resultRGB' % checker_handle)
    params.ReferenceFloat("presence", '%s:resultR' % mix_handle)
    rman_sg_material.sg_node.SetBxdf([manifold, checker, checker2, float3_1, float3_2, mix, bxdf])    

def gp_material_fill_gradient(mat, rman, rman_sg_material, handle):
    gp_mat = mat.grease_pencil
    col = gp_mat.fill_color[:3]
    col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.fill_color[3]
    mix_color = gp_mat.mix_color[:3]
    mix_color = color_utils.linearizeSRGB(mix_color)  
    mat_sg_nodes = []

    bxdf_handle = '%s-PxrConstant' % handle
    bxdf = rman.SGManager.RixSGShader("Bxdf", "PxrConstant", bxdf_handle)


    manifold_handle = '%s-PxrManifold2D' % handle
    manifold = rman.SGManager.RixSGShader("Pattern", "PxrManifold2D", manifold_handle) 
    params = manifold.params 
    params.SetFloat("scaleS", gp_mat.pattern_scale[0])
    params.SetFloat("scaleT", gp_mat.pattern_scale[1])    
    params.SetFloat("angle", -math.degrees(gp_mat.pattern_angle))  
    #params.SetFloat("offsetS", gp_mat.pattern_shift[0]) 
    #params.SetFloat("offsetT", gp_mat.pattern_shift[1])     
    params.SetInteger("invertT", 0)   
    mat_sg_nodes.append(manifold)

    ramp_handle = '%s-PxrRamp' % handle
    ramp = rman.SGManager.RixSGShader("Pattern", "PxrRamp", ramp_handle) 
    params = ramp.params 
    params.SetInteger('rampType', 0) 
    
    colors = []    
    colors.append(col[:3])
    colors.append(col[:3])
    colors.append(mix_color[:3])
    colors.append(mix_color[:3])

    params.SetFloatArray('colorRamp_Knots', [0.0, 0.0, 1.0, 1.0], 4)
    params.SetColorArray('colorRamp_Colors', colors, 4)
    params.SetString('colorRamp_Interpolation', 'linear')
    params.ReferenceStruct("manifold", '%s:result' % manifold_handle)  
    mat_sg_nodes.append(ramp)

    params = bxdf.params
       
    params.ReferenceColor("emitColor", '%s:resultRGB' % ramp_handle)    
    
    #params.SetFloat('presence', alpha)
    mat_sg_nodes.append(bxdf)
    rman_sg_material.sg_node.SetBxdf(mat_sg_nodes)   

def gp_material_fill_solid(mat, rman, rman_sg_material, handle):
    gp_mat = mat.grease_pencil
    col = gp_mat.fill_color[:3]
    col = color_utils.linearizeSRGB(col)
    alpha = gp_mat.fill_color[3]

    bxdf_handle = '%s-PxrConstant' % handle
    bxdf = rman.SGManager.RixSGShader("Bxdf", "PxrConstant", bxdf_handle)
    
    params = bxdf.params
    params.SetColor('emitColor', col)     
    params.SetFloat('presence', alpha)
    rman_sg_material.sg_node.SetBxdf([bxdf])       