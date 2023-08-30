def formatDuration(durationInSeconds: float) -> str:
    """
    Parameters:
    durationInSeconds: fractional seconds (same as what would be returned by `time.perf_counter()`)
    """
    s, ms = divmod(round(durationInSeconds * 1000), 1000)

    if not s > 0.0:
        return f'{int(ms)}ms'
    
    m, s = divmod(s, 60)
    
    if not m > 0.0:
        return f'{s}.{ms:03d}'

    h, m = divmod(m, 60)

    if not h > 0.0:
        return f'{m}:{s:02d}.{ms:03d}'

    return f"{h}:{m:02d}:{s:02d}.{ms:03d}"