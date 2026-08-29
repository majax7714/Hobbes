#!/bin/sh
# Install one Temurin JDK under /usr/local/java-<major>, checksum-verified.
#   hobbes-jdk-install <major> <release e.g. jdk-21.0.12.1+1> <sha256>
set -eu
major=$1; release=$2; sha=$3
ver=$(echo "$release" | sed 's/^jdk-//; s/+/_/')
enc=$(echo "$release" | sed 's/+/%2B/')
url="https://github.com/adoptium/temurin${major}-binaries/releases/download/${enc}/OpenJDK${major}U-jdk_x64_linux_hotspot_${ver}.tar.gz"
curl -fsSL -o /tmp/jdk.tgz "$url"
echo "$sha  /tmp/jdk.tgz" | sha256sum -c -
mkdir -p "/usr/local/java-$major"
tar -xzf /tmp/jdk.tgz -C "/usr/local/java-$major" --strip-components=1
rm /tmp/jdk.tgz
