# technology : {optimizer_name: django_name}
# Rapid sand filtration, single: 18

# the optimized parameters can be found in the <technology>_results.json files
optimized_dv_pystim_to_dst = {
    18: {
        'surf_m2': 10,
        'lbed_m': 135,
    },
    # ...
}
inputs__techprop_dst_to_pystim = {
    18: {
        'filter area': <property number 'surf_m2'>,
        'sand_media_grain_size': <property number 'sand_media_grain_size'>,
        'sand_porosity': <property number 'sand_porosity'>,
        'sand filter bed height': <property number 'lbed_m'>,
    },
}
inputs_wq_dst_to_pystim ={}