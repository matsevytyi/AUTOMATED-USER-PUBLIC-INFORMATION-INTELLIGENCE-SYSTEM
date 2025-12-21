from backend.wrappers.llm_wrapper import chat

from models import InformationPiece, ChatSession, ChatMessage

import backend.engines.rag_engine

import json

class AssistantService:
    def __init__(self, db):
        self.db = db
        pass
    
    def get_session_messages(self, session_id):
        
        msgs = ChatMessage.query.filter_by(session_id=session_id)\
            .order_by(ChatMessage.created_at.asc())\
            .all()
            
        out = [m.to_dict() for m in msgs]
        
        return out 
    
    def create_session(self, current_user_email, report_id, title, save_history):
        try:
            # Reuse a single session per user+report
            existing = ChatSession.query.filter_by(
                user_email=current_user_email, 
                report_id=report_id
            ).first()
            
            if existing:
                return existing

            cs = ChatSession(
                user_email=current_user_email, 
                report_id=report_id, 
                title=title, 
                save_history=save_history
            )
            
            cs_copy = cs
            self.db.session.add(cs)
            self.db.session.commit()
            
            return cs_copy 
        except Exception as e:
            self.db.session.rollback()
            print(f'Failed to create chat session: {e}')
            return None
    
    def get_answer(self, user_msg, scope, datapiece_ids, session_id, provider):
        
        session = ChatSession.query.filter_by(id=session_id).first()
        if not session:
            raise Exception("Session not found")
        
        # Build context
        context = []
        try:
            if scope == 'datapieces' and datapiece_ids:
                piece = InformationPiece.query.filter(
                    InformationPiece.id.in_(datapiece_ids)
                ).first()
                user_msg += "\n\nContext:\n" + str(piece.to_dict())
                
                # Similar pieces for datapiece
                similar = InformationPiece.query.filter(
                    InformationPiece.report_id.in_(piece.report_id),
                    InformationPiece.category_id == piece.category_id,
                    InformationPiece.id != piece.id
                ).order_by(InformationPiece.created_at.desc()).limit(5).all()
                
                for sp in similar:
                    user_msg += "\n\nSimilar pieces:\n" + str(sp.to_dict())
            else:
                # Whole report: include recent pieces for the report
                context = [
                    str(p.to_dict()) 
                    for p in InformationPiece.query.filter_by(report_id=session.report_id)
                        .order_by(InformationPiece.created_at.desc())
                        .limit(40)
                        .all()
                ]
                
                user_msg += "\n\nContext:\n" + '\n\n'.join(context) if context else ""
                
        except Exception as e:
            print(f'Failed loading datapiece context: {e}')

        # Save user message if history is enabled
        try:
            if session.save_history:
                um = ChatMessage(session_id=session.id, sender='user', content=user_msg)
                self.db.session.add(um)
                self.db.session.commit()
        except Exception:
            self.db.session.rollback()

        # Prepare messages for LLM
        if scope == 'datapieces' and datapiece_ids:
            system_prompt = {
                'role': 'system',
                'content': """You respond as a friendly assistant who explains risks and insights based on the provided sources and helps to maintain awareness about digital-footprint security and protecting yourself online. Evaluate information that you see as a whole (but part os smth bigger meaning there may be nore datapieces), its meaning, security implications, and exposure risks. 

                                The report is about the user who asked and contains information that was already found about him.

                                Do not hallucinate.
                                Draw conclusions from the datapiece (and context) and from similar datapieces (provided under Similar Pieces).
                                If you do not know, say exactly that.
                                Do not reveal technical details (such as IDs).
                                You may give information based on links, context snippets, and titles.

                                When answering:
                                Make the explanation short and understandable.
                                Elaborate on whether having this datapiece exposed online (not published intentionally, but visible to others) is dangerous and why.
                                Clarify privacy or safety issues related to <strong>user-exposed data</strong>.
                                Provide any other helpful comments.
                                Tell the user exactly which source link the information came from.

                                Use HTML tags (i.e. <strong>, <italic> or <br>) instead of Markdown.
                                                    """ }
        else:
            system_prompt = {
            'role': 'system',
            'content': """You respond as a friendly assistant who explains risks and insights based on the entire provided report.
                            The report may contain multiple datapieces about the user, and your job is to evaluate the document as a whole, its meaning, security implications, and exposure risks.
                            The report is about the user who asked and contains information that was already found about him.

                            Do not hallucinate.
                            Base all conclusions strictly on the content of the report and its context.
                            If something is unclear or missing, state exactly that.
                            Do not reveal technical identifiers (such as full IDs, tokens, hashes).
                            You may summarize or refer to information based on links, context snippets, titles, or descriptive fields included in the report.

                            When answering:
                            Keep explanations short and easy to understand.
                            Evaluate whether having this entire report exposed online is dangerous, and explain why.
                            Mention any notable privacy, security, or reputation concerns.
                            Provide any other relevant commentary that could help the user protect themselves.
                            Always specify where each insight comes from using the given source links or references.

                            Use HTML tags (e.g., <strong>, <italic>, <br>) instead of Markdown.
                            """ }
        
        messages = [system_prompt, {'role': 'user', 'content': user_msg}]

        # Call LLM abstraction with fallback
        try:
            llm_result = chat(
                provider or 'groq', 
                messages, 
                context, 
                fallback=['openai', 'local']
            )
            reply = llm_result.get('reply') if isinstance(llm_result, dict) else str(llm_result)
            sources = llm_result.get('sources', []) if isinstance(llm_result, dict) else []
        except Exception as e:
            print(f'LLM call failed: {e}')
            reply = 'Failed to get response from LLM.'
            sources = []

        # Save assistant reply if history is enabled
        try:
            if session.save_history:
                am = ChatMessage(
                    session_id=session.id, 
                    sender='assistant', 
                    content=reply, 
                    meta=json.dumps({'sources': sources})
                )
                self.db.session.add(am)
                self.db.session.commit()
        except Exception:
            self.db.session.rollback()

        return reply, sources

    