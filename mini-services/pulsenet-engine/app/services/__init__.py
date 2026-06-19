"""Application services — orchestrate feeds + agents + compute + repo.

Services are the only layer that ties everything together; routes call services,
services call repo/agents/compute. This keeps each layer independently testable.
"""
