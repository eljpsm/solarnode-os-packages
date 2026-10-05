# SolarNode Application - Setup Bluetooth

This directory contains support for building the `solarnode-app-setup-bluetooth`
package, which provides the `net.solarnetwork.node.setup.bluetooth` plugin. The
plugin turns the Bluetooth setup radio provided by the
`solarnode-bluetooth-setup` package on only while it is needed:

- while a `bt-setup` operational mode is active
- while the node has been unable to reach SolarNetwork for a period of time
- or always

See the [CHANGELOG](./CHANGELOG.md) for release information.

This package requires `solarnode-bluetooth-setup` 4.0 or later, which provides
the `solarcfg bluetooth` helper the plugin drives.

# Build requirements

You must clone the
[solarnetwork-build](https://github.com/SolarNetwork/solarnetwork-build/)
repository in this directory (or make a symlink to it). Packaging is done via
`make` with [ant](https://ant.apache.org/) and
[fpm](https://github.com/jordansissel/fpm). To get started:

```sh
sudo apt-get install git git-lfs ant ruby ruby-dev build-essential
sudo gem install --no-document fpm

# if you have solarnetwork-build checked out elsewhere, then
ln -s /path/to/solarnetwork-build

# or, clone solarnetwork-build directly (note that git-lfs is required)
git clone https://github.com/SolarNetwork/solarnetwork-build.git
```

# Building

Run `make` to build the package, which will produce
`solarnode-app-setup-bluetooth_VERSION_all.deb` in this directory.
