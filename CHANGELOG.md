thx
===

v0.4.0a1
--------

Alpha release

- Implemented 'list' and 'dump-config' commands
- Added `--watch` mode
- Added `job.show_output` flag
- Support for Windows cmd.exe

```
$ git shortlog -s v0.3.0...v0.4.0a1
    25	John Reese
    11	dependabot[bot]
```


v0.3.0
------

Feature release

- Better CLI presentation of jobs and results using Rich (#14)
- New option `--live` to skip version detection (#15)
- Better tracking of runtime versions available (#15)
- Fixed benchmarking on Windows due to lack of time precision

```
$ git shortlog -s v0.2.0...v0.3.0
     8	John Reese
```


v0.2.0
------

Alpha release

- Essential configuration structure
- Run jobs in separate contexts/virtualenvs in parallel
- Mark jobs as run once, or run all steps in parallel
- See stdout/stderr from failed jobs
- Get overall failure status
- Basic wall clock benchmarking
- Reuse virtualenvs when possible

See `pyproject.toml` for example job specs.

```
$ git shortlog -s v0.1.0...v0.2.0
    16	John Reese
    10	dependabot[bot]
```


v0.1.0
------

Initial release

* Basic implementation of configuration, contexts, and job running

```
$ git shortlog -s v0.1.0
    37	John Reese
     2	dependabot[bot]
```

