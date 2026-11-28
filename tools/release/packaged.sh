#!/bin/sh
set -eu
target=${CARGO_TARGET_DIR:-target}
out=$target/packaged
rm -rf "$target/package" "$out"
mkdir -p "$out/vendor" "$out/root"
cargo package --workspace --locked --no-verify
cargo vendor --locked --versioned-dirs "$out/vendor" > /dev/null
for crate in "$target"/package/*.crate; do
  tar -xzf "$crate" -C "$out/vendor"
  checksum=$(sha256sum "$crate" | cut -d ' ' -f 1)
  printf '{"files":{},"package":"%s"}' "$checksum" \
    > "$out/vendor/$(basename "$crate" .crate)/.cargo-checksum.json"
done
set -- "$target"/package/pycg-[0-9]*.crate
test "$#" -eq 1
version=$(basename "$1" .crate)
version=${version#pycg-}
cargo install pycg --version "=$version" --locked --root "$out/root" \
  --config 'source.crates-io.replace-with="packaged"' \
  --config "source.packaged.directory=\"$out/vendor\""
