def compositor(*args, **kwargs):
    
    import glob
    import subprocess
    from landslide_pipeline.pipeline import OUTPUT
    import os

    # Check for planet data:

    is_planet = True if kwargs.get('items', None) is not None else False

    if is_planet:
        visual_filenames = [os.path.join(OUTPUT['output_path'], prefix) for prefix in kwargs.get('image_prefixes') if "Visual" in prefix]
        analytic_filenames = [os.path.join(OUTPUT['output_path'], prefix) for prefix in kwargs.get('image_prefixes') if "Analytic" in prefix]
        if len(visual_filenames) > 0:
            output_name = os.path.join(OUTPUT['output_path'],OUTPUT['output_path'] + "_Visual.tif")
            arg = ['gdal_merge.py', '-o', output_name, '-createonly', '-of', 'GTiff', '-co',
                   'COMPRESS=LZW'] + visual_filenames
            subprocess.call(arg)
            compositor_index = 0
            for visual_filename in visual_filenames:
                arg = ['gdal_merge.py', '-o', '/tmp/visual_' + str(compositor_index) + '.tif', '-of', 'GTiff', '-co',
                       'COMPRESS=LZW', output_name, visual_filename]
                subprocess.call(arg)
                compositor_index += 1
            arg = ['compositor', '-q', '-o', output_name]
            for index in range(compositor_index):
                arg += ['-i', '/tmp/visual_' + str(index) + '.tif']
            subprocess.call(arg)
        if len(analytic_filenames) > 0:
            output_name = os.path.join(OUTPUT['output_path'], OUTPUT['output_path'] + "_Analytic.tif")
            arg = ['gdal_merge.py', '-o', output_name, '-createonly', '-of', 'GTiff', '-co',
                   'COMPRESS=LZW'] + analytic_filenames
            subprocess.call(arg)
            arg = ['compositor', '-q', '-o', output_name]
            for analytic_filename in analytic_filenames:
                arg += ['-i', analytic_filename]
            subprocess.call(arg)
    else:
        pathrow_dirs = glob.glob(OUTPUT['output_path'] + '/P*R*')
        for pathrow_dir in pathrow_dirs:
            scenes = glob.glob(pathrow_dir + '/*')
            first_image = glob.glob(scenes[0] + '/*_RGB.TIF')[0]
            arg = ['gdal_merge.py', '-o', pathrow_dir + '/' + os.path.basename(pathrow_dir) + '.TIF', '-createonly', first_image]
            subprocess.call(arg)
    
            arg = ['compositor', '-q', '-o', pathrow_dir + '/' + os.path.basename(pathrow_dir) + '.TIF']
            for scene in scenes:
                scene_filename = glob.glob(scene + '/*_RGB.TIF')[0]
                arg += ['-i', scene_filename]
    
            subprocess.call(arg)
    
            if kwargs.get('cloudless_scene', None) is None:
                kwargs['cloudless_scenes'] = [pathrow_dir + '/' + os.path.basename(pathrow_dir) + '.TIF']
            else:
                kwargs['cloudless_scenes'] += [pathrow_dir + '/' + os.path.basename(pathrow_dir) + '.TIF']
    
    return kwargs
    