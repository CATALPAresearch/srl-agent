const path = require("path");
const webpack = require("webpack");
const { VueLoaderPlugin } = require("vue-loader");
const TerserPlugin = require("terser-webpack-plugin");

module.exports = (env, options) => {
  const isProduction = options.mode === "production";

  return {
    entry: "./src/main.js",
    output: {
      path: path.resolve(__dirname, "../backend/static/lti"),
      publicPath: "/static/lti/",
      filename: "app-lazy.js",
      chunkFilename: "[id].app-lazy.js?v=[contenthash]",
      // loaded via require.js (standalone index.html and Moodle)
      library: { type: "amd" },
    },
    module: {
      rules: [
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
        {
          test: /\.vue$/,
          loader: "vue-loader",
        },
        {
          test: /\.js$/,
          loader: "babel-loader",
          exclude: /node_modules/,
        },
      ],
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src/"),
      },
      extensions: [".tsx", ".ts", ".js", ".vue", ".json"],
    },
    devServer: {
      historyApiFallback: true,
      headers: {
        "Access-Control-Allow-Origin": "*",
      },
      allowedHosts: "all",
      server: "https",
      hot: true,
      client: { overlay: true },
    },
    performance: {
      hints: false,
    },
    devtool: isProduction ? false : "source-map",
    plugins: [
      new VueLoaderPlugin(),
      // Vue 3 compile-time feature flags (esm-bundler build)
      new webpack.DefinePlugin({
        __VUE_OPTIONS_API__: JSON.stringify(true),
        __VUE_PROD_DEVTOOLS__: JSON.stringify(false),
        __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: JSON.stringify(false),
      }),
    ],
    watchOptions: {
      ignored: /node_modules/,
    },
    optimization: isProduction
      ? { minimizer: [new TerserPlugin({ parallel: true })] }
      : {},
    externals: {
      "core/ajax": { amd: "core/ajax" },
      "core/str": { amd: "core/str" },
      "core/modal_factory": { amd: "core/modal_factory" },
      "core/modal_events": { amd: "core/modal_events" },
      "core/fragment": { amd: "core/fragment" },
      "core/yui": { amd: "core/yui" },
      "core/localstorage": { amd: "core/localstorage" },
      "core/notification": { amd: "core/notification" },
      jquery: { amd: "jquery" },
      jqueryui: { amd: "jqueryui" },
    },
  };
};
