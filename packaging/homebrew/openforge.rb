# OpenForge — Homebrew formula (v5 line).
class Openforge < Formula
  desc "OpenForge — Forge intelligent code, locally."
  homepage "https://github.com/neuralforgeio/openforge"
  url "https://github.com/neuralforgeio/openforge/archive/refs/tags/v5.0.2.tar.gz"
  license "MIT"
  depends_on "python@3.11"
  def install
    bin.install_symlink libexec/"bin/openforge"
  end
  test do
    system "#{bin}/openforge", "--version"
  end
end
