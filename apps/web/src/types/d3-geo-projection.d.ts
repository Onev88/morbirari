// `d3-geo-projection` no publica tipos (@types/d3-geo-projection no existe). Solo se usa
// `geoProject`, que proyecta una geometría GeoJSON a través de una proyección aplicando
// el corte del antimeridiano y el recorte de la esfera (lo que geoPath hace al dibujar).
declare module "d3-geo-projection" {
  import type { GeoProjection } from "d3-geo";
  import type { GeoJsonObject } from "geojson";
  export function geoProject(object: GeoJsonObject, projection: GeoProjection): GeoJsonObject | null;
}
