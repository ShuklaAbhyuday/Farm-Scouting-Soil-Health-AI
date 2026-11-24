declare module 'react-leaflet-draw' {
  import { FeatureGroupProps } from 'react-leaflet';
  import { Control } from 'leaflet';
  import * as React from 'react';

  export interface EditControlProps extends FeatureGroupProps {
    onEdited?: Function;
    onDrawStart?: Function;
    onDrawStop?: Function;
    onDrawVertex?: Function;
    onEditStart?: Function;
    onEditMove?: Function;
    onEditResize?: Function;
    onEditVertex?: Function;
    onEditStop?: Function;
    onDeleted?: Function;
    onDeleteStart?: Function;
    onDeleteStop?: Function;
    onCreated?: Function;
    onMounted?: Function;
    draw?: Control.DrawConstructorOptions;
    edit?: Control.EditOptions;
    position?: Control.Position;
  }

  export class EditControl extends React.Component<EditControlProps> {}
}
