# Coreos-nvidia

Precompiled nvidia drivers and nvidia container tools to use Nvidia GPUs on Coreos kube-aws nodes.

Each release of this repository contains two tarballs:
- `container-runtime_coreos_<COREOS_VERSION>.tar.gz`
    - This tarball contains the Nvidia Docker runtime files, and needs to be extracted to '/' of a new node.
- `nvidia-binaries_coreos_<COREOS_VERSION>-<NVIDIA_VERSION>.tar.gz`
    - These are optional precompiled binaries for faster provisioning of a new node.

## Usage instructions

- Add the buildscripts from [https://github.com/Clarifai/coreos-nvidia/](https://github.com/Clarifai/coreos-nvidia/), especially [https://github.com/Clarifai/coreos-nvidia/pull/4/files](https://github.com/Clarifai/coreos-nvidia/pull/4/files) to `userdata/cloud-config-worker`. Look for `{{ if .Gpu.Nvidia.IsEnabledOn .InstanceType }}`. (we use https://github.com/kubernetes-incubator/kube-aws/ which uses these scripts)
- Add the following script as well (this will extract the container runtime files to `/` on the node):
  ```
    - path: /opt/bin/nvidia-install-container-runtime.sh
      owner: root:root
      permissions: 0755
      content: |
        #!/bin/sh
        # Install Nvidia container runtime files (static libs/bins from Github)
        source /etc/lsb-release
        wget https://github.com/Alliander/Coreos-nvidia/releases/download/$DISTRIB_RELEASE/container-runtime_coreos_$DISTRIB_RELEASE.tar.gz -O - | tar -C / -zxvf -
  
        mount /usr/local/bin
  
        mkdir -p /etc/ld.so.conf.d/ 2>/dev/null
        echo "/opt/nvidia-docker/lib" > /etc/ld.so.conf.d/nvidia-docker.conf
        ldconfig
  ```
- The `mount /usr/local/bin` will bind mount /opt/bin to /usr/local/bin, because /usr/local/bin isn't writable and /opt/bin isn't included in the Docker PATH variable.
- Include it is as systemd service:
  ```
    - name: nvidia-install-container-runtime.service
      enable: false
      content: |
        [Unit]
        Description=Install NVIDIA container runtime files
        After=network.target
  
        [Service]
        Type=oneshot
        RemainAfterExit=true
        ExecStart=/opt/bin/nvidia-install-container-runtime.sh
  
        [Install]
        WantedBy=multi-user.target
  ```
- Add a drop-in to `docker.service` to make this service a dependency of Docker:
  ```
    {{- if .Gpu.Nvidia.IsEnabledOn .InstanceType }}
    - name: 50-nvidia-container-runtime.conf
      content: |
        [Unit]
        Requires=nvidia-install-container-runtime.service
        After=nvidia-install-container-runtime.service
    {{- end }}
  ```
- Run `kube-aws update` to test!
- Login on node and check Journal to see if everything  runs well.

### Usage in Kubernetes

For Kubernetes, also the Nvidia device plugin daemonset is required. See [https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/#deploying-nvidia-gpu-device-plugin](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/#deploying-nvidia-gpu-device-plugin).

- Apply the `nvidia-device-plugin.yml` to your cluster.
- Check if the pod starts correctly:
  ```
    kubectl -n kube-system get pods -l name=nvidia-device-plugin-ds
  ```
- TODO: in order to get this plugin working, we needed to run this pod in privileged mode. 
- If the device plugin pod starts correctly, you can test it by deploying the tensorflow pod in the pods directory. 
    - Open a shell in the tensorflow pod and run the `test.py` file (you'll first need to copy it to the pod).
    - If `test.py` runs correctly, it will do a matrix calculation on the GPU (and print the GPU name):
      ```
        I tensorflow/core/common_runtime/gpu/gpu_device.cc:1103] Created TensorFlow device (/job:localhost/replica:0/task:0/device:GPU:0 with 14873 MB memory) -> physical GPU (device: 0, name: Tesla V100-SXM2-16GB, pci bus id: 0000:00:1e.0, compute capability: 7.0)
      ```

### Using pre-compiled drivers (optional)
- To speed-up node provisioning time, we can fetch the binaries from Github instead of compiling them ourself.
- Look for `path: /opt/nvidia-build/build-and-install.sh` in the `userdata/cloud-config-worker` file.
- Replace 
  ``` 
    bash -x build.sh {{.Gpu.Nvidia.Version}}
  ```

  with:

  ```
    wget https://github.com/Alliander/Coreos-nvidia/releases/download/$DISTRIB_RELEASE/nvidia-binaries_coreos_$DISTRIB_RELEASE-{{.Gpu.Nvidia.Version}}.tar.gz -O - | tar -zxvf - || bash -x build.sh {{.Gpu.Nvidia.Version}}
  ```
- The construction with `||` makes sure it will 'fallback' to compiling the driver, if no pre-built binaries can be found for the given CoreOs/Nvidia driver combination.

## Making a new release

When we update the cluster with a new CoreOs version, we need to make a new Github release with the two new `.tar.gz`. files.

### Updating Nvidia container runtime files
- First, we need to check if new container binaries / libraries are needed: the current libraries are compiled against glibc 2.28, so if the new CoreOs release still uses the same glibc we can reuse the old binaries.
- If we can reuse the old binaries, just make a new tarball of them:
  ```
    $ cd container-runtime
    $ tar zcvf ../container-runtime_coreos_<COREOS_VERSION>.tar.gz *
  ```
- The coreos version can be found in `/etc/lsb-release` on the node.
- Upload the tarball to a new Github release on [https://github.com/Alliander/Coreos-nvidia/releases/new](https://github.com/Alliander/Coreos-nvidia/releases/new). Use the new Coreos version as git tag.

If we do need new binaries (or if you just want to use the latest Nvidia container runtime), then we need to download hem from Nvidia.
- The latest version of the Nvidia container runtime files can be found at: [https://nvidia.github.io/nvidia-container-runtime/](https://nvidia.github.io/nvidia-container-runtime/).
- However, they are only packages for rpm and deb. And the URL's are not public available (only the package managers can 'find' them).
- Luckily we can find the exact URL in an Arch Linux build scripts, see: [https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=libnvidia-container](https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=libnvidia-container) and [https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=nvidia-container-runtime](https://aur.archlinux.org/cgit/aur.git/tree/PKGBUILD?h=nvidia-container-runtime). (see the `source_x86_64=` line).
- Download those files and extract the files with something like `rpm2cpio`.
- Check if they match the glibc version of the Coreos node (TODO: how? trial-and-error by running them on the node?).
- If they match, add them to the container-runtime directory of this Github repo (and commit them!).
- Make a new Github release for the given Coreos version (see the beginning of this subsection).

### Updating the pre-compiled Nvidia binaries
Luckily, updating the Nvidia driver binaries is much easier than updating containter runtime:

- Provision a new Coreos gpu node. It will see that there are no pre-compiled Nvidia driver binaries, so it will fallback to compiling them itself.
- Build the binaries and keep the exported tars:
    - cd /opt/nvidia-build/
    - ./build.sh --keep
- Retrieve the following files from the node in `/opt/nvidia-build/:
    - tools-<NVIDIA_VERSION>.tar.bz2
    - modules-<COREOS_VERSION>-<NVIDIA_VERSION>.tar.bz2
    - libraries-<NVIDIA_VERSION>.tar.bz2
- Add them to a tarball:
  ```
    $ tar zcvf `nvidia-binaries_coreos_<COREOS_VERSION>-<NVIDIA_VERSION>.tar.gz` tools-<NVIDIA_VERSION>.tar.bz2 modules-<COREOS_VERSION>-<NVIDIA_VERSION>.tar.bz2 libraries-<NVIDIA_VERSION>.tar.bz2
  ```
- The coreos version can be found in `/etc/lsb-release` on the node.
- Upload the tarball to a new Github release on [https://github.com/Alliander/Coreos-nvidia/releases/new](https://github.com/Alliander/Coreos-nvidia/releases/new). Use the new Coreos version as git tag.
- Check if the file is retrieved correctly by provisioning a  new Coreos gpu node.

<!-- vim: set ts=4 sw=4 et: -->
