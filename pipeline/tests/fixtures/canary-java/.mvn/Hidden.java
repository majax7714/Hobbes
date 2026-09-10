package canary;

/** Planted under .mvn/ (the 2026-09-10 review's path): a source the
 *  resolve pass must never see. Lane A does not discover dot-directories,
 *  so it is on no index stage either. */
public class Hidden {}
