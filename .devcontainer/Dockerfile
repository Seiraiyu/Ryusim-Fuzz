FROM ghcr.io/seiraiyu/ryusim-fuzz:latest

ARG REMOTE_USER=vscode
ARG REMOTE_UID=1000
ARG REMOTE_GID=1000

# Build Verilator from source (cocotb requires >= 5.036)
RUN apt-get update && apt-get install -y --no-install-recommends \
        autoconf flex bison ccache g++ git help2man libfl2 libfl-dev \
        make perl python3 zlib1g-dev && \
    git clone --depth 1 --branch v5.042 \
        https://github.com/verilator/verilator /tmp/verilator && \
    cd /tmp/verilator && \
    autoconf && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    rm -rf /tmp/verilator

# Build Icarus Verilog from source
RUN apt-get install -y --no-install-recommends \
        autoconf bison flex g++ gperf && \
    git clone --depth 1 --branch v13_0 \
        https://github.com/steveicarus/iverilog /tmp/iverilog && \
    cd /tmp/iverilog && \
    sh autoconf.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    rm -rf /tmp/iverilog && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Remove existing user/group with conflicting IDs
RUN if getent passwd ${REMOTE_UID} >/dev/null 2>&1; then \
        existing_user=$(getent passwd ${REMOTE_UID} | cut -d: -f1); \
        userdel -r ${existing_user} 2>/dev/null || userdel ${existing_user}; \
    fi && \
    if getent group ${REMOTE_GID} >/dev/null 2>&1; then \
        existing_group=$(getent group ${REMOTE_GID} | cut -d: -f1); \
        groupdel ${existing_group} 2>/dev/null || true; \
    fi

# Create non-root user
RUN groupadd --gid ${REMOTE_GID} ${REMOTE_USER} && \
    useradd --uid ${REMOTE_UID} --gid ${REMOTE_GID} -m -s /bin/bash ${REMOTE_USER} && \
    echo "${REMOTE_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Node.js (needed for Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Persist bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R ${REMOTE_USER} /commandhistory

# Create workspace and config directories
RUN mkdir -p /workspace /home/${REMOTE_USER}/.claude && \
    chown -R ${REMOTE_USER}:${REMOTE_USER} /workspace /home/${REMOTE_USER}/.claude

USER ${REMOTE_USER}

# Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | bash

ENV PATH="/home/${REMOTE_USER}/.local/bin:$PATH"
ENV HOME=/home/${REMOTE_USER}
