# D-01: Homebrew formula (STUB — syntax-valid Ruby, not yet published).
class OpenForgeAgent < Formula
  desc "OpenForge — local-first AI agent"
  homepage "https://github.com/neuralforgeio/nexa-agent"
  url "https://github.com/neuralforgeio/nexa-agent/archive/refs/tags/v4.12.0.tar.gz"
  license "MIT"

  depends_on "python@3.11"

  def install
    # STUB: real bottle + pip install steps go here once the release ships.
    bin.install_symlink libexec/"bin/nexa"
  end

  test do
    system "#{bin}/nexa", "--version"
  end
end
