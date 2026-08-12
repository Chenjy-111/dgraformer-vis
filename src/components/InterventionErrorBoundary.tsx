import { Component, type ErrorInfo, type ReactNode } from 'react';

export class InterventionErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true}}
  componentDidCatch(error:Error,info:ErrorInfo){console.error('Intervention lab render failed',error,info)}
  render(){
    if(this.state.failed)return <section className="bg-[#f5f8fb] px-5 py-12"><div className="mx-auto max-w-[1180px] rounded-xl border border-red-200 bg-white p-5 text-sm text-red-700">The intervention visualization could not be rendered. No substitute scientific result was generated. The rest of DGraInsight remains available.</div></section>;
    return this.props.children;
  }
}
