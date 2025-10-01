# Multi-stage Dockerfile for Jekyll documentation build
FROM ruby:3.1-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    build-base \
    git \
    nodejs \
    npm

# Set working directory
WORKDIR /app

# Copy Gemfile and Gemfile.lock
COPY . .

# Install Ruby dependencies
RUN bundle lock --add-platform x86_64-linux-musl && bundle config set --local deployment 'true' && \
    bundle config set --local without 'development test' && \
    bundle install

# Build Jekyll site
ENV JEKYLL_ENV=production
RUN bundle exec jekyll build

FROM scratch
COPY --from=builder /app/_site /