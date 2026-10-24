FROM ubuntu:22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install base tools, Python, Node.js, Git
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install common testing tools
RUN pip3 install --no-cache-dir pytest ruff mypy

# Create non-root user
RUN useradd -m -s /bin/bash sandboxuser

WORKDIR /workspace
RUN chown -R sandboxuser:sandboxuser /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER sandboxuser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
