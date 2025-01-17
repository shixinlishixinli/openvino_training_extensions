#!/usr/bin/env python3
#
# Copyright (C) 2019 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

from argparse import ArgumentParser
import os
import warnings
import cv2
import skimage
import numpy as np
from openvino.inference_engine import IENetwork, IEPlugin


def build_argparser():
    parser = ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="Path to an .xml file with a trained model.")
    parser.add_argument("--device", help="Specify the target device to infer on. (default: %(default)s)",
                        choices=["CPU", "GPU", "MYRIAD"], default="CPU")
    parser.add_argument('--output_dir', default=None, help='Output debugirectory')
    parser.add_argument('input_image', help='Image')
    return parser.parse_args()


def load_ir_model(model_xml, device):
    model_bin = os.path.splitext(model_xml)[0] + ".bin"

    # initialize plugin and read IR
    plugin = IEPlugin(device=device)
    net = IENetwork(model=model_xml, weights=model_bin)
    exec_net = plugin.load(network=net)

    input_blobs = net.inputs.keys()
    inputs = [(b, net.inputs[b].shape) for b in input_blobs]

    out_blob = next(iter(net.outputs))
    del net

    return exec_net, plugin, inputs, out_blob


def image_to_blob(image, shape):
    blob = image.copy()
    blob = blob.transpose((2, 0, 1))  # from HWC to CHW
    blob = blob.reshape(shape)
    return blob


def blob_to_img(blob):
    blob = blob.transpose((1, 2, 0))   # from CHW to HWC
    blob = np.clip(blob, 0.0, 1.0)

    # Suppression skimage warning:
    #    UserWarning: Possible precision loss when converting from float32 to uint8
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        blob = skimage.img_as_ubyte(blob)
    return blob

def main():
    args = build_argparser()
    exec_net, _, inputs, out_blob = load_ir_model(args.model, args.device)

    # Prepare input blobs
    ih, iw = inputs[0][1][2:]
    image = cv2.imread(args.input_image)
    if image.shape[0] != ih or image.shape[1] != iw:
        image = image[0:ih, 0:iw]

    cubic = cv2.resize(image, (inputs[1][1][3], inputs[1][1][2]), interpolation=cv2.INTER_CUBIC)

    blob1 = image_to_blob(image, (inputs[0][1]))
    blob2 = image_to_blob(cubic, (inputs[1][1]))

    # inference
    result = exec_net.infer(inputs={inputs[0][0]: blob1, inputs[1][0]: blob2})

    # Postprocessing
    out_img = blob_to_img(result[out_blob][0])

    outpur_dir = args.output_dir if args.output_dir else os.path.dirname(args.input_image)
    out_path = os.path.join(outpur_dir, "sr_" + os.path.basename(args.input_image))
    cv2.imwrite(out_path, out_img)
    print("Saved: ", out_path)

if __name__ == "__main__":
    main()
