def load_data(*args, **kwargs):

    if kwargs.get('image_prefixes', None) is not None and kwargs.get('items', None) is not None:
        return kwargs

    from landslide_pipeline.pipeline import LOCATION, TIMES, SATELLITE_INFO, OUTPUT, DEBUG
    import os
    import planet.api as api
    import requests
    from landslide_pipeline.pipeline import OUTPUT

    # Set up client:

    api_key = "58613e03d31d4476ae132fbe8bd0afca"
    os.environ["PL_API_KEY"] = api_key

    client = api.ClientV1()

    # Set up query:

    sat_info = SATELLITE_INFO

    coordinates = [
         [
            [
                LOCATION['min_longitude'],
                LOCATION['min_latitude']
            ],
            [
                LOCATION['max_longitude'],
                LOCATION['min_latitude']
            ],
            [
                LOCATION['max_longitude'],
                LOCATION['max_latitude']
            ],
            [
                LOCATION['min_longitude'],
                LOCATION['max_latitude']
            ],
            [
                LOCATION['min_longitude'],
                LOCATION['min_latitude']
            ]
         ]
      ]
    query_and_geofilter = {
        "item_types": sat_info,
        "filter": {
            "type": "AndFilter",
            "config":
                [
                    {
                        "type": "RangeFilter",
                        "field_name": "cloud_cover",
                        "config": {"lte": 0.5}
                    },
                    {
                        "type": "GeometryFilter",
                        "field_name": "geometry",
                        "config":
                            {
                                "type": "Polygon",
                                "coordinates": coordinates
                            }
                    },
                    {
                        "type": "DateRangeFilter",
                        "field_name": "acquired",
                        "config":
                            {
                                "gt": TIMES['start'],
                                "lte": TIMES['end']
                            }
                    }
                ]
        }
    }

    items = client.quick_search(query_and_geofilter, page_size=250)

    num_items = 0
    for _ in items.items_iter(250):
        num_items += 1
    print('Query returned ' + str(num_items) + ' items.')

    # Download items:
    output_directory = os.path.join(os.getcwd(), OUTPUT['output_path'])
    try:
        os.mkdir(output_directory)
    except:
        pass

    from landslide_pipeline.pipeline import MAX_ACQUISITIONS
    from concurrent.futures import ThreadPoolExecutor, as_completed
    executor = ThreadPoolExecutor(max_workers = MAX_ACQUISITIONS)

    all_futures = []

    def activate_and_download(item):

        # setup auth
        session = requests.Session()
        session.auth = (api_key, '')

        assets = client.get_assets(item).get()
        asset_futures = []

        def activate_and_download_asset_type(asset_type):
            activated = False
            while not activated:
                dataset = \
                    session.get(
                        ("https://api.planet.com/data/v1/item-types/" +
                        "{}/items/{}/assets/").format(item['properties']['item_type'], item['id']))
                # extract the activation url from the item for the desired asset
                item_activation_url = dataset.json()[asset_type]["_links"]["activate"]
                # request activation
                response = session.post(item_activation_url)
                activated = (response.status_code == 204)
                if not activated:
                    print("Waiting for activation of: ", item['id'])
                    import time
                    time.sleep(30.0)
            asset = client.get_assets(item).get()[asset_type]
            callback = api.write_to_file(directory=output_directory, callback=None, overwrite=True)
            name = client.download(asset, callback=callback).wait().name
            return name, item

        if assets.get('visual', None) is not None:
            asset_futures += [executor.submit(activate_and_download_asset_type, 'visual')]
        if assets.get('analytic', None) is not None and not DEBUG:
            asset_futures += [executor.submit(activate_and_download_asset_type, 'analytic')]

        return asset_futures

    import numpy as np

    potential_items_to_download = [item_i for item_i in items.items_iter(250)]
    items_to_download = [potential_items_to_download[x] for x in np.random.choice(len(potential_items_to_download), MAX_ACQUISITIONS, replace=False)] if len(potential_items_to_download) > MAX_ACQUISITIONS else potential_items_to_download

    for item_i in items_to_download:
        all_futures += activate_and_download(item_i)

    print('Activating and downloading ' + str(len(items_to_download)) + ' items.')

    results = []

    for result in as_completed(all_futures):
        results += [result.result()]
        print('Finished downloading asset.', result.result()[0])

    # Put all filenames of all assets into kwargs['image_prefixes']:

    this_args = {'start': TIMES['start'],
                 'end': TIMES['end'],
                 'satellite': SATELLITE_INFO,
                 'output_path': OUTPUT['output_path']}
    image_prefixes = []
    items_list = []
    for result in results:
        image_prefixes += [result[0]]
        items_list += [result[1]]
    kwargs['image_prefixes'] = image_prefixes
    kwargs['items'] = items_list
    kwargs.update(this_args)
    return kwargs

def reproject_assets(*args, **kwargs):

    from landslide_pipeline.pipeline import OUTPUT
    # Save items (if not done so already, making sure they are stored in OUTPUT['output_path']):
    output_projection = OUTPUT['output_projection']
    for (item, filename) in zip(kwargs['items'], kwargs['image_prefixes']):
        import os
        full_filename = os.path.join(OUTPUT['output_path'], filename)
        if int(item['properties']['epsg_code']) != output_projection:
            import subprocess as sp
            arg = ['gdalwarp', '-s_srs', 'EPSG:' + str(item['properties']['epsg_code']), '-t_srs', 'EPSG:' + str(OUTPUT['output_projection']), full_filename, '/tmp/tmpreproj.tif']
            sp.call(arg)
            arg = ['rm', '-f', full_filename]
            sp.call(arg)
            arg = ['mv', '/tmp/tmpreproj.tif', full_filename]
            sp.call(arg)
            print('Reprojected: ', full_filename)
        else:
            print('Did not reproject: ', filename)

    return kwargs

