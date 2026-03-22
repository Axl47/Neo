{
  description = "A development environment for Neo";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python313
            uv
            jdk17
          ];

          shellHook = ''
            echo "Environment loaded!"
            echo "Python: $(python --version)"
            echo "uv: $(uv --version)"
            echo "Java: $(java --version | head -n1)"
          '';
        };
      }
    );
}
