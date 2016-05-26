## Indico's Article Clustering Demo

### Data
Currently, the data available for clustering is of Finance articles. The source can be found in the S3 bucket: `s3://corpii/Finance`.


### Setup
1. Required Environment Variables (~/.bashrc)

    ```bash
    export INDICO_API_KEY="" # Needs access to the themeextraction server
    export CUSTOM_INDICO_API_KEY="" # Needs access to the custom collections
    export AWS_ACCESS_KEY_ID="" # Access to the S3 for contact@indico.io
    export AWS_SECRET_ACCESS_KEY="" # Access to the S3 for contact@indico.io
    export AWS_HOSTED_ZONE_ID="Z2GXF43FTQVWH2" # us-west-2
    ```
2. (Optional) Useful scripts for process control & using [tmux](https://gist.github.com/MohamedAlaa/2961058) (~/.bashrc)

    ```bash
    # i.e. `die python` - this will kill existing python processes
    die() {
        proc=$(echo $1 | sed 's/^\(.\)/[\1]/')
        sudo kill -9 $(ps aux | grep $proc | awk '{print $2}')
    }

    # i.e. `attach 1` - this will attach the screen 1 for tmux
    attach() {
      tmux attach-session -t $1
    }
    ```
3. Don't forget to source `~/.bashrc`
4. Save the contents of `./scripts/setup.sh` to a file with `sudo chown -x setup.sh` permissions. Run the script.

5. Run elasticsearch by running the `./scripts/run_elasticsearch_host.sh` script in a tmux screen.

6. Either [restore elasticsearch data](wiki-link-for-elasticsearch-here) from a backup, or run data ingress to populate the elasticsearch store.

### Running Data Ingress
```bash
# With the data in <ClusterRSS root>/inputxl
# With a <ClusterRSS root>/completed.txt file containing finished file names
python -m cluster.search.load_data [number_of_processes] 2>&1 | tee raw.log
```

### Running the Server
```bash
python -m indicluster.app
# navigate to localhost:8002/text-mining in your browser
```
