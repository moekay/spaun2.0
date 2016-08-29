import os
import numpy as np
import numpy.ma as ma
import argparse
import matplotlib.pyplot as plt


# --------------------- DISP_PROBE_DATA CODE DEFAULTS ---------------------
supported_data_version = 5.0
default_filename = ''

# ----- Add current directory to system path ---
cur_dir = os.getcwd()

# --------------------- PROCESS SYSTEM ARGS ---------------------
parser = argparse.ArgumentParser(description='Script for displaying recorded' +
                                 ' probed data generated by the run_spaun.py' +
                                 ' script.')
parser.add_argument(
    'data_filename', type=str,
    help='Probe data filename.')
parser.add_argument(
    '--showgrph', action='store_true',
    help='Supply to show graphing of probe data.')
parser.add_argument(
    '--showanim', action='store_true',
    help='Supply to show animation of probe data.')
parser.add_argument(
    '--showiofig', action='store_true',
    help='Supply to show Spaun input/output figure.')
parser.add_argument(
    '--data_dir', type=str, default=os.path.join(cur_dir, 'data'),
    help='Directory to store output data.')
parser.add_argument(
    '--legend_pos', type=str, default='best',
    help='Legend position argument to use for matplotlib plots.')
parser.add_argument(
    '--trange', type=float, nargs=2, default=None,
    help=('Minimum and maximum time values (in seconds) to display on the ' +
          'graphs. Provided as two values e.g. --trange MIN MAX.'))

args = parser.parse_args()

data_filename = os.path.join(args.data_dir, args.data_filename)
data_filename = data_filename.replace('"', '')

show_grphs = args.showgrph
show_io = args.showiofig
show_anim = args.showanim
if not (show_grphs or show_io or show_anim):
    show_grphs = True

# --------------------- LOAD SIM DATA ---------------------
gen_trange = False
if data_filename.endswith('.npz'):
    config_filename = data_filename[:-4] + '_cfg.npz'
    probe_data = np.load(data_filename)

elif data_filename.endswith('.h5'):
    # H5 file format (nengo_mpi)
    config_dir, filename = os.path.split(data_filename[:-3])
    nameparts = filename.split('+')
    config_filename = os.path.join(config_dir,
                                   '+'.join(nameparts[:2]) + '_cfg.npz')

    import h5py
    probe_data = h5py.File(data_filename)

    gen_trange = True
else:
    raise RuntimeError('Filename: %s - File format not supported.' %
                       data_filename)

# --------------------- LOAD MODEL & PROBE CONFIG DATA ---------------------
config_data = np.load(config_filename)

data_version = 0 if 'version' not in config_data.keys() else \
    config_data['version'].item()
if int(data_version) != int(supported_data_version):
    raise Exception('Unsupported data version number. Expected %i, got %i.'
                    % (supported_data_version, data_version))

vocab_dict = config_data['vocab_dict'].item()
ncount_dict = config_data['ncount_dict'].item()
image_shapes = config_data['image_dict'].item()
path_limits = config_data['path_dict'].item()
probe_labels = config_data['label_dict'].item()
image_dict = dict()
motor_dict = dict()
sim_dt = config_data['dt']

# --------------------- GENERATE T RANGE ---------------------
if not gen_trange:
    trange = probe_data['trange']
else:
    data_len = probe_data[probe_data.keys()[0]].shape[0]
    trange = np.arange(0, data_len * sim_dt, sim_dt)

if args.trange is None:
    trange_inds = np.arange(trange.shape[0])
else:
    trange_min, trange_max = args.trange
    trange_inds = np.where((trange >= trange_min) & (trange <= trange_max))
t_data = trange[trange_inds]

# --------------------- DISPLAY PROBE DATA ---------------------
print "\nDISPLAYING PROBE DATA."

fig_list = []


# Function to handle closing of one figure window, and close all other figures
def handle_close(fig, fig_list):
    fig_list.pop(fig_list.index(fig))
    if len(fig_list) > 0:
        plt.close(fig_list[0])


# Helper function to calculate differences in images (for show_io)
def rmse(x1, x2):
    return np.sqrt(np.sum((x1 - x2) ** 2))


# Helper function to adjust path coordinates to help plotting
def adjust_path_coords(path_data, path_limits, new_limits):
    path_l_limit, path_u_limit = path_limits
    path_range = path_u_limit - path_l_limit
    new_l_limit, new_u_limit = new_limits
    new_range = new_u_limit - new_l_limit

    return ((path_data - path_l_limit) * (new_range / path_range) +
            new_l_limit)


# Helper function to plot legends
def plot_legend(str_list, loc='right', labelspacing=0, max_per_row=5.0,
                fontsize='medium'):
    lgd = plt.legend(str_list, loc=loc, labelspacing=labelspacing,
                     ncol=int(np.ceil(len(str_list) / max_per_row)))
    lgd_text = lgd.get_texts()
    plt.setp(lgd_text, fontsize=fontsize)

# --------------------- DISPLAY GRAPHED DATA ---------------------
# Get presentation interval (for image graphs)
present_interval = probe_data['present_interval']
aspect_equal_y_margin = present_interval * 0.25

if show_grphs:
    graph_list = config_data['graph_list']

    print "GRAPH LIST: "
    print graph_list

    title_list = [[]]
    grph_list = [[]]
    for p in graph_list:
        if p == '..':
            grph_list.append([])
            title_list.append([])
        elif p[0] == '!':
            pass
        elif p[:-2].replace('.', '').isdigit():
            grph_list[-1].append(p)
        else:
            title_list[-1].append(p.replace('**', ''))

    for n, fig in enumerate(grph_list):
        f = plt.figure()
        f.canvas.mpl_connect('close_event',
                             lambda evt, fig=f, fig_list=fig_list:
                             handle_close(fig, fig_list))
        fig_list.append(f)

        if len(title_list[n]) > 0:
            plt.suptitle(title_list[n][-1])

        max_r = len(fig)
        for r, probe_id_str in enumerate(fig):
            # Get probe id and probe plot options
            probe_opts = probe_id_str[-2:]
            probe = probe_id_str[:-2]

            # Matplotlib settings
            plt.subplot(max_r, 1, r + 1)
            colormap = plt.cm.gist_ncar
            graymap = plt.cm.gray

            # Figure out if probe plot needs a legend
            disp_legend = probe_opts[-1] == '*'

            # Get probe data (filtered by min and max tranges)
            if probe_opts[0] != 'p':
                p_data = probe_data[probe][trange_inds]

            if probe_opts[0] == 'V':
                # Vector with vocabulary plots
                vocab = vocab_dict[probe]
                num_classes = len(vocab.keys)

                plt.gca().set_color_cycle([colormap(i) for i in
                                           np.linspace(0, 0.9, num_classes)])
                for i in range(num_classes):
                    plt.plot(t_data,
                             np.dot(p_data, vocab.vectors.T)[:, i])
                if disp_legend:
                    plot_legend(vocab.keys)
            elif probe_opts[0] == 'v':
                # vector without vocabulary plots
                num_classes = p_data[-1].size
                if num_classes < 30:
                    plt.gca().set_color_cycle([colormap(i) for i in
                                               np.linspace(0, 0.9,
                                                           num_classes)])
                    for i in range(num_classes):
                        plt.plot(t_data, p_data[:, i])
                    if disp_legend:
                        plot_legend(map(str, range(num_classes)))
                else:
                    plt.plot(t_data, p_data)
            elif probe_opts[0] == 's':
                # Spike display options
                height = 0.75  # Height of 1 spike
                spike_value = 1.0 / sim_dt

                # Find the neurons to display
                # Choose random selection of top 35% of fastest firing neurons
                spike_totals = np.sum(p_data, axis=0)

                total_neuron_count = spike_totals.shape[0]
                disp_neuron_count = min(ncount_dict[probe], total_neuron_count)
                top_neuron_count = int(max(total_neuron_count * 0.35,
                                           disp_neuron_count))

                spike_ind_sorted = np.argsort(spike_totals)[-top_neuron_count:]
                spike_ind_selected = np.random.permutation(spike_ind_sorted)
                spike_ind_selected = spike_ind_selected[:disp_neuron_count]
                spike_data = p_data[:, spike_ind_selected]

                # Set the color cycle to grayscale
                plt.gca().set_color_cycle(
                    [graymap(i) for i in
                     np.linspace(0, 0.8, disp_neuron_count)])

                # Triple the trange (spike plotting oddities)
                strange = ma.array(t_data).repeat(3)

                # Plot the spike plot
                for nn in range(disp_neuron_count):
                    sdata = ma.array((spike_data[:, nn]).repeat(3))
                    sdata[0::3] *= (1 + nn - height / 2.0) / spike_value
                    sdata[1::3] *= (1 + nn + height / 2.0) / spike_value
                    sdata[2::3] = ma.masked
                    plt.plot(strange, sdata)

                # Display a legend if specified?
                if disp_legend:
                    plot_legend(map(str, spike_ind_sorted + 1))

                plt.ylim(0, disp_neuron_count + 1)
            elif probe_opts[0] == 'i':
                # Image plot option
                if probe not in image_dict:
                    # Raw image (vector) data hasn't been processed. Do
                    # processing now.
                    # Calculate root square error to figure out when the image
                    # changes
                    im_rse = np.sqrt(np.sum(np.diff(p_data, axis=0) ** 2,
                                            axis=1))
                    # Figure out where the changes take place
                    im_timeline = \
                        np.concatenate(([0], np.where(im_rse > 0.1)[0] + 1))
                    image_dict[probe] = im_timeline
                else:
                    im_timeline = image_dict[probe]

                # Get image dimensions
                im_shape = image_shapes[probe]
                im_height = im_width = present_interval

                # Plot the images
                for im_ind in im_timeline:
                    im_data = p_data[im_ind, :]
                    im_time = t_data[im_ind]
                    plt.imshow(im_data.reshape(im_shape),
                               cmap=plt.get_cmap('gray'),
                               interpolation='nearest', aspect='equal',
                               extent=(im_time, im_time + im_width,
                                       0, im_height))
                    plt.plot([im_time] * 2,
                             [-aspect_equal_y_margin,
                              im_height + aspect_equal_y_margin], 'w')
                plt.yticks([])
                plt.gca().set_axis_bgcolor('black')
                plt.ylim(-aspect_equal_y_margin,
                         im_height + aspect_equal_y_margin)
            elif probe_opts[0] == 'p':
                probes = probe.split('.')
                probe_path = probe = probes[0]
                if len(probes) > 1:
                    probe_pen = probes[1]

                    # Figure out when the pen is up and when the pen is down
                    pen_d_threshold = 0.5
                    pen_u_threshold = 0.25

                    pen_raw_data = probe_data[probe_pen][trange_inds]
                    pen_data = np.zeros(shape=pen_raw_data.shape)

                    # Anything above pen_d_threshold is considered down
                    pen_data[pen_raw_data >= pen_d_threshold] = 1

                    # Anything between pen_d_threshold and p_u_threshold has
                    # to be calculated (by taking the state of pen_data for
                    # one timestep previous)
                    pen_u_d_ind = np.where((pen_raw_data < pen_d_threshold) &
                                           (pen_raw_data > pen_u_threshold))[0]
                    for ind in pen_u_d_ind:
                        pen_data[ind] = pen_data[ind - 1]
                    pen_data = pen_data.flatten()

                    # Figure out where the crossing points are
                    pen_change_inds = np.where(np.diff(pen_data))[0] + 1
                    # Split the time data into different chunks corresponding
                    # to each pen state
                    t_change = np.split(t_data, pen_change_inds)
                    # Split the path data into different chunks corresponding
                    # to each pen state
                    path_change = np.split(probe_data[probe_path],
                                           pen_change_inds)
                else:
                    # If there is no pen down information, then just plot the
                    # path at the end of the graph
                    pen_change_inds = [0]
                    pen_data = [1]
                    t_change = [[0], [t_data[-1]]]
                    path_change = [[0], probe_data[probe_path][trange_inds]]

                # Get path limits
                path_x_limit, path_y_limit = path_limits[probe_path]

                # Iterate through the different pen states and plot them
                for j, ind in enumerate(pen_change_inds):
                    # Get the pen state
                    pen_state = pen_data[ind]
                    # Plot if pen is down
                    if pen_state:
                        tstart = t_change[j + 1][-1] - present_interval
                        path_x = \
                            adjust_path_coords(path_change[j + 1][:, 0],
                                               path_x_limit,
                                               [tstart,
                                                tstart + present_interval])
                        path_y = \
                            adjust_path_coords(path_change[j + 1][:, 1],
                                               path_y_limit,
                                               [0, present_interval])
                        plt.plot(path_x, path_y, 'b')

                plt.gca().set_aspect('equal')
                plt.ylim(-aspect_equal_y_margin,
                         present_interval + aspect_equal_y_margin)
                plt.yticks([])
            else:
                raise RuntimeError('Probe option: "%s" not supported' %
                                   probe_opts[0])

            plt.xlim([t_data[0], t_data[-1]])
            if probe_labels[probe] is None:
                plt.ylabel('%i,%i' % (n + 1, r + 1))
            else:
                plt.ylabel(probe_labels[probe])

            # Compress plots (no vertical spaces between subplots)
            f.subplots_adjust(hspace=0.05, bottom=0.05, left=0.05, right=0.98,
                              top=0.95)
            plt.setp([a.get_xticklabels() for a in f.axes[:-1]], visible=False)

if show_anim or show_io:
    anim_config = config_data['anim_config']

    print "ANIMATION CONFIG: "
    print anim_config

if show_io:
    from _spaun.modules.vision.data import VisionDataObject

    # TODO: UPDATE TO USE NEW CODE FROM ABOVE
    vis_stim_config = anim_config[0]
    vis_stim_probe_id_str = vis_stim_config['data_func_params']['data']
    vis_stim_data = np.array(probe_data[vis_stim_probe_id_str])

    arm_data_dict = anim_config[1]['data_func_params']
    ee_probe_id_str = arm_data_dict['ee_path_data']
    ee_data = np.array(probe_data[ee_probe_id_str])
    pen_probe_id_str = arm_data_dict['pen_status_data']
    pen_data = np.array(probe_data[pen_probe_id_str])

    arm_data_scale = anim_config[1]['plot_type_params']['xlim'][1]

    A_img = VisionDataObject().get_image('A')[0]
    num_cols = 0
    curr_col_ind = 0

    plot_data = []
    plot_type = []

    pen_down = False
    pen_down_ind = -1

    img_ind_filter = []
    path_len_filter = 200

    prev_img = np.zeros(vis_stim_data.shape[1])
    for i in range(vis_stim_data.shape[0]):
        img = vis_stim_data[i, :]

        img_shown = np.sum(img) > 0
        if (not pen_down and pen_data[i] > 0.5 and not img_shown):
            pen_down = True
            pen_down_ind = i
        elif (pen_down and (pen_data[i] < 0.25 or img_shown or
                            i == vis_stim_data.shape[0] - 1)):
            pen_down = False
            path_data = ee_data[pen_down_ind:i, :]
            if path_data.shape[0] > path_len_filter:
                if len(plot_data) <= 0:
                    plot_data.append([])
                    plot_type.append([])
                plot_data[-1].append(path_data)
                plot_type[-1].append("path")

        if rmse(prev_img, img) > 0.1:
            # Img data is an 'A', so reset things
            if rmse(img, A_img) < 0.1:
                if len(plot_data) > 0:
                    num_cols = max(num_cols, len(plot_data[-1]))
                plot_data.append([])
                plot_type.append([])
                curr_col_ind = 0
            if len(plot_data) <= 0:
                plot_data.append([])
                plot_type.append([])
            if (curr_col_ind in img_ind_filter) or len(img_ind_filter) == 0:
                plot_data[-1].append(np.array(img))
                plot_type[-1].append("im")
            prev_img = img
            curr_col_ind += 1

    # Get number of columns (gotta do this here to take into account last row)
    # added to the plot_data array
    num_cols = max(num_cols, len(plot_data[-1]))

    plt.figure(figsize=(min(2 * num_cols, 18), min(2 * len(plot_data), 12)))
    for i in range(len(plot_data)):
        for j in range(len(plot_data[i])):
            plt.subplot(len(plot_data), num_cols, i * num_cols + j + 1,
                        aspect=1)
            if plot_type[i][j] == 'im':
                # Reshape to 28 * 28 (TODO: FIX for generic images?)
                im_data = plot_data[i][j].reshape((28, 28))
                plt.imshow(im_data, cmap=plt.get_cmap('gray'),
                           interpolation='nearest', aspect='equal')
                plt.xticks([])
                plt.yticks([])
            else:
                plt.plot(plot_data[i][j][:, 0], plot_data[i][j][:, 1])
                plt.xticks([])
                plt.yticks([])
                plt.xlim(-arm_data_scale, arm_data_scale)
                plt.ylim(-arm_data_scale, arm_data_scale)
    plt.tight_layout()

if show_anim:
    from _spaun.animation import ArmAnim, DataFunctions, GeneratorFunctions

    subplot_width = anim_config[-1]['subplot_width']
    subplot_height = anim_config[-1]['subplot_height']
    max_subplot_cols = anim_config[-1]['max_subplot_cols']

    num_plots = len(anim_config) - 1
    num_cols = num_plots if num_plots < max_subplot_cols else max_subplot_cols
    num_rows = int(np.ceil(1.0 * num_plots / max_subplot_cols))

    # Make the figure to pass to the animation object
    # Note: not hooked into close handler of other figures so that you can
    #       independently close animation figure while keeping others open
    #       (and vice versa)
    f = plt.figure(figsize=(num_cols * subplot_width,
                            num_rows * subplot_height))

    # Make the animation object
    anim_obj = ArmAnim(None, (num_rows, num_cols), f)
    func_map = {}

    # Loop through the animation configuration list and add each subplot
    for i, config in enumerate(anim_config[:-1]):
        # Subplot location
        subplot_row = i / max_subplot_cols
        subplot_col = i % max_subplot_cols

        # Create the data object to use for the animation
        data_func_obj = getattr(DataFunctions, config['data_func'])
        data_func_params = {}
        for param_name in config['data_func_params']:
            if isinstance(config['data_func_params'][param_name], str):
                data_func_params[param_name] = \
                    probe_data[config['data_func_params'][param_name]]
            else:
                data_func_params[param_name] = \
                    config['data_func_params'][param_name]
        data_func = data_func_obj(**data_func_params)

        # Add the data function to the function map
        func_map[config['key']] = data_func

        # Add animation subplot to anim_obj
        plot_type_params = dict(config['plot_type_params'])
        plot_type_params.setdefault('key', config['key'])
        plot_type_params.setdefault('tl_loc', (subplot_row, subplot_col))
        getattr(anim_obj, 'add_' + config['plot_type'])(**plot_type_params)

    # Assign the proper data generator function to the animation object and
    # start it
    data_gen_func_params = anim_config[-1]['generator_func_params']
    anim_obj.data_gen_func = \
        lambda: GeneratorFunctions.keyed_data_funcs(trange, func_map,
                                                    **data_gen_func_params)
    anim_obj.start(interval=10)

plt.show()
probe_data.close()
